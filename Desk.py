import asyncio
import struct
from asyncio import Task
from typing import Any, Callable, Union
import logging
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
        logging.debug('Retrieving desk height')
        try:
            result = await self.__desk_connection.read_gatt_char(self.uuid_height)
            parsed = Desk.__unpack_data(result)
            return parsed
        except bleak.exc.BleakError as e:
            logging.warning('Error retrieving desk height')
            logging.warning(e)
            return 0, 0

    async def move_up(self):
        try:
            await self.__desk_connection.write_gatt_char(self.uuid_cmd, self.cmd_up)
        except bleak.exc.BleakError as e:
            pass

    async def move_down(self):
        logging.debug('Moving desk up 1 unit.')
        try:
            await self.__desk_connection.write_gatt_char(self.uuid_cmd, self.cmd_down)
        except bleak.exc.BleakError as e:
            logging.warning('Error moving desk up 1 unit.')
            logging.warning(e)
            pass

    async def move_to(self, target: float) -> None:
        logging.debug("Moving desk to {}".format(target))
        start_height, start_speed = await self.get_desk_height()
        logging.debug("Currently at {}".format(start_height))

        # The desk moves in centimers, so makes no sense to try and hit milimeter precision.
        if abs(target - start_height) <= 20:
            logging.debug("Desk is close enough, not moving")
            return None

        direction = self.cmd_down if target < start_height else self.cmd_up
        move_completed = asyncio.get_event_loop().create_future()

        # The _move callback is called whenever the height changes.
        # On every invocation the current height is checked.
        # If the threshold is reached, resolve the future.
        # Otherwise, schedule a task every 6 updates.
        # 6 is a magic number.
        update_counter = 0
        retries = 0

        def _move(current_height_mm: float, speed_mm_s: float):
            nonlocal update_counter
            nonlocal direction
            nonlocal retries
            update_counter = update_counter + 1

            # If the desk moved (speed was not 0.0) it must be
            # checked to see if it is at the right height.
            # If it's not at the right height yet, only send another command
            # if the desk sent around 6 updates.
            if abs(current_height_mm - target) <= 20:
                logging.debug("Desk moved within threshold: {}".format(abs(current_height_mm - target)))
                asyncio.create_task(self.remove_callback(self.uuid_height, _move))
                move_completed.set_result(True)

            # When the speed of the desk is 0.0, one of two things happened.
            #  1. The desk is at the end or beginning, which is fine, but we have to stop.
            #  2. The desk is being pushed on, so it can't go up enough, so we have to stop.
            # Stopping means resolving the future so move_to_target can return.
            elif speed_mm_s == 0:
                if retries >= 1:
                    logging.debug("Desk stopped moving, but did not reach target.")
                    asyncio.create_task(self.remove_callback(self.uuid_height, _move))
                    move_completed.set_result(True)
                else:
                    logging.debug("Desk stopped moving, trying again!")
                    await asyncio.sleep(2)
                    retries = retries + 1
                    asyncio.create_task(self.move_down())

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

    async def __attempt_connect(self):
        logging.debug("Attempting connection to desk")
        try:
            await self.__desk_connection.connect()
        except Exception as e:
            logging.debug("Attempt failed.")
            return False
        return True

    async def __reconnect(self):
        logging.debug("Attempting to reconnect to desk")
        self.__desk_connection = BleakClient(self.mac_address)
        try:
            while not self.__desk_connection.is_connected:
                if await self.__attempt_connect():
                    logging.debug("Connection established")
                    return True
                else:
                    logging.debug("Attempt to connect failed, waiting for 30 seconds..")
                    await asyncio.sleep(30)

            await self.__initialize_monitor()
            await self.get_desk_height()
        except Exception as e:
            logging.error("An error occurred reconnecting to the desk: {}".format(e))
            return False

    async def __monitor_connection(self):
        if not self.__desk_connection.is_connected:
            logging.debug("Monitor detected desk is disconnected")
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
            logging.debug("Height changed: height: {}, speed: {}".format(current_height_mm, speed_mm_s))
            callbacks = self.__callbacks[self.uuid_height]

            for cb in callbacks:
                cb(current_height_mm, speed_mm_s)

        await self.__install_debug_callback()
        await self.__desk_connection.start_notify(self.uuid_height, __height_changed)

    async def __install_debug_callback(self):
        def _cb(height, speed):
            if speed != 0:
                logging.debug("Height: {}, speed: {}".format(height, speed))

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
        print("Connected to desk!")

    async def connect_to_desk(self) -> Any:
        await self.__initialize()
