import asyncio
import struct
from asyncio import Task
from typing import Any, Callable, Union

import bleak.exc
from bleak import BleakClient


class Desk:
    uuid_height: str = "99fa0021-338a-1024-8a49-009c0215f78a"
    uuid_cmd: str = "99fa0002-338a-1024-8a49-009c0215f78a"
    uuid_reference_input: str = "99fa0031-338a-1024-8a49-009c0215f78a"

    cmd_up = bytearray(struct.pack("<H", 71))
    cmd_down = bytearray(struct.pack("<H", 70))
    cmd_stop = bytearray(struct.pack("<H", 255))

    mac_address: Union[str, None] = None
    __desk_connection: Union[BleakClient, None] = None
    __monitor_task: Union[None, Task[Any]] = None
    __callbacks: dict[str, list[Any]] = {uuid_height: set()}

    def __init__(self, address, callback) -> None:
        self.mac_address = address
        self.__desk_connection = None
        self.install_callback(self.uuid_height, callback)

    # ---------------------------------------------------------------------------
    # Helper Methods
    @staticmethod
    def __raw_to_millimeter(raw: float) -> float:
        return raw / 10

    @staticmethod
    def __millimeter_to_raw(millimeter: float) -> float:
        return millimeter * 10

    @staticmethod
    def __raw_to_millimeter_per_second(raw: float) -> float:
        return raw / 100

    @staticmethod
    def __human_to_machine_height(millimeter: float) -> float:
        return millimeter - 620

    @staticmethod
    def __machine_to_human_height(millimeter: float) -> float:
        return millimeter + 620

    @staticmethod
    def __unpack_data(data: bytearray):
        height_raw, speed = struct.unpack("<Hh", data)
        current_height_mm = Desk.__raw_to_millimeter(height_raw)
        speed_mm_s = Desk.__raw_to_millimeter_per_second(speed)
        return current_height_mm, speed_mm_s

    # ---------------------------------------------------------------------------
    # Desk Control

    async def get_desk_height(self):
        try:
            result = await self.__desk_connection.read_gatt_char(self.uuid_height)
            parsed = Desk.__unpack_data(result)
            return parsed
        except bleak.exc.BleakError as e:
            return 0, 0

    async def move_up(self):
        try:
            await self.__desk_connection.write_gatt_char(self.uuid_cmd, self.cmd_up)
        except bleak.exc.BleakError as e:
            pass

    async def move_down(self):
        try:
            await self.__desk_connection.write_gatt_char(self.uuid_cmd, self.cmd_down)
        except bleak.exc.BleakError as e:
            pass

    async def move_to(self, target: float) -> None:
        print("Moving to ")
        print(target)
        start_height, start_speed = await self.get_desk_height()

        # The desk moves in centimers, so makes no sense to try and hit milimeter precision.
        if abs(target - start_height) <= 20:
            return None

        direction = self.cmd_down if target < start_height else self.cmd_up
        move_completed = asyncio.get_event_loop().create_future()

        # The _move callback is called whenever the height changes.
        # On every invocation the current height is checked.
        # If the threshold is reached, resolve the future.
        # Otherwise, schedule a task every 6 updates.
        # 6 is a magic number.
        update_counter = 0

        def _move(current_height_mm: float, speed_mm_s: float):
            nonlocal update_counter
            nonlocal direction
            update_counter = update_counter + 1

            # If the desk moved (speed was not 0.0) it must be
            # checked to see if it is at the right height.
            # If it's not at the right height yet, only send another command
            # if the desk sent around 6 updates.
            if abs(current_height_mm - target) <= 20:
                asyncio.create_task(self.remove_callback(self.uuid_height, _move))
                move_completed.set_result(True)

            # When the speed of the desk is 0.0, one of two things happened.
            #  1. The desk is at the end or beginning, which is fine, but we have to stop.
            #  2. The desk is being pushed on, so it can't go up enough, so we have to stop.
            # Stopping means resolving the future so move_to_target can return.
            elif speed_mm_s == 0:
                asyncio.create_task(self.remove_callback(self.uuid_height, _move))
                move_completed.set_result(True)

            elif update_counter % 6 == 0:
                if direction == self.cmd_up:
                    asyncio.create_task(self.move_up())
                else:
                    asyncio.create_task(self.move_down())

        self.install_callback(self.uuid_height, _move)
        if direction == self.cmd_up:
            asyncio.create_task(self.move_up())
        else:
            asyncio.create_task(self.move_down())

    # ---------------------------------------------------------------------------
    # Connection Monitor

    async def __reconnect(self):
        self.__desk_connection = BleakClient(self.mac_address)
        try:
            await self.__desk_connection.connect()
            await self.__initialize_monitor()
            await self.get_desk_height()
        except Exception as e:
            print("An error occurred reconnecting to the desk: {}".format(e))
            return False

    async def __monitor_connection(self):
        if not self.__desk_connection.is_connected:
            print("Desk disconnected")
            await self.__reconnect()
        else:
            await self.get_desk_height()

        await asyncio.sleep(2)
        asyncio.create_task(self.__monitor_connection())

    async def __initialize_monitor(self):
        if self.__monitor_task:
            self.__monitor_task.cancel()
        self.__monitor_task = asyncio.create_task(self.__monitor_connection())

    # ---------------------------------------------------------------------------
    # Callback Machinery

    def install_callback(self, event: str, callback: Callable[[float, float], Any]):
        self.__callbacks[event].add(callback)

    async def remove_callback(self, event: str, callback: Callable[[float, float], Any]):
        if callback in self.__callbacks[event]:
            self.__callbacks[event].remove(callback)

    async def __initialize_callbacks(self):
        def __height_changed(_sender: int, data: bytearray):
            current_height_mm, speed_mm_s = self.__unpack_data(data)
            callbacks = self.__callbacks[self.uuid_height]

            for cb in callbacks:
                cb(current_height_mm, speed_mm_s)

        await self.__install_debug_callback()
        await self.__desk_connection.start_notify(self.uuid_height, __height_changed)

    async def __install_debug_callback(self):
        def _cb(height, speed):
            print("Height: {}, speed: {}".format(height, speed))

        self.install_callback(self.uuid_height, _cb)

    # ---------------------------------------------------------------------------
    # Init

    async def __initialize(self):
        self.__desk_connection = BleakClient(self.mac_address)
        try:
            await self.__desk_connection.connect()
            await self.__initialize_monitor()
            await self.__initialize_callbacks()
        except Exception as e:
            print("An error occurred connecting to the desk: {}".format(e))
            return False

    async def connect_to_desk(self) -> Any:
        await self.__initialize()
