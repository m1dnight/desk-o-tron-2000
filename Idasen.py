import asyncio
import logging
import os
import struct
from typing import Any

from bleak import BleakClient, BleakError  # type: ignore

logging.basicConfig(format='%(asctime)s %(message)s', encoding='utf-8', level=logging.DEBUG)
logging.getLogger().addHandler(logging.FileHandler(r'idasen.log'))


class ConnectException(Exception):
    pass


class Idasen:
    # Instance fields.
    connection: Any
    mac_address: str

    # Bluetooth UUIDs.
    bt_uuid_height: str = "99fa0021-338a-1024-8a49-009c0215f78a"
    bt_uuid_cmd: str = "99fa0002-338a-1024-8a49-009c0215f78a"
    bt_uuid_reference_input: str = "99fa0031-338a-1024-8a49-009c0215f78a"

    # Bluetooth command constants.
    bt_cmd_up: bytearray = bytearray(struct.pack("<H", 71))
    bt_cmd_down: bytearray = bytearray(struct.pack("<H", 70))
    bt_cmd_stop: bytearray = bytearray(struct.pack("<H", 255))

    def __init__(self, mac_address: str):
        self.connection = None
        self.mac_address = mac_address

    # ---------------------------------------------------------------------------
    # Connection to device.

    async def attempt_connect_n_times(self, attempts_left: int, backoff: int) -> BleakClient:
        """
        Attempts to connect to the desk for attempts_left times. The process waits backoff seconds before the next attempt.
        Raises an exception if all attempts fail.
        :param attempts_left: attempts to connect. Use -1 for infinite attempts.
        :param backoff: seconds between each attempt.
        :return: the connection.
        """
        if attempts_left > 0 or attempts_left == -1:
            try:
                connection = await self.attempt_connect()
                return connection
            except ConnectException:
                remaining_attempts = -1 if attempts_left == -1 else attempts_left - 1
                logging.error("Attempt to connect to desk failed. Trying {} more times in {} seconds.".format(remaining_attempts, backoff))
                await asyncio.sleep(backoff)
                await self.attempt_connect_n_times(remaining_attempts, backoff)
        else:
            raise ConnectException("No attempts succeeded to connect to the desk.")

    async def reconnect_waiter(self, disconnect_event):
        """
        Monitors the event in case of a disconnect. When the event is raised, the waiter keeps trying to establish the connection.
        If a connection is established, a new waiter is created so this one can terminate.
        :param disconnect_event:
        """
        logging.debug("Reconnect waiter waiting for disconnect event.")
        await disconnect_event.wait()
        try:
            self.connection = await self.attempt_connect_n_times(-1, 30)
            logging.info("Reconnect waiter successfully reconnected to the desk.")
        except ConnectException as e:
            logging.error("Reconnect waiter could not connect to desk after {} attempts.".format(-1))
            raise ConnectException("Reconnect waiter could not find and connect to desk. Ensure the MAC address is correct and the desk is powered on.")

    async def attempt_connect(self) -> BleakClient:
        """
        Attempts to connect to the desk once. Throws an exception if the connection fails.
        :return: the connection.
        """
        logging.debug("Attempting to connect to desk.")

        disconnected_event = asyncio.Event()

        def disconnected_callback(client):
            disconnected_event.set()

        try:
            connection = BleakClient(self.mac_address, disconnected_callback=disconnected_callback)
            await connection.connect()
            logging.info("Connection attempt succeeded.")
            asyncio.create_task(self.reconnect_waiter(disconnected_event))
            return connection

        except BleakError as e:
            logging.error("Connection attempt failed.")
            raise ConnectException("Could not connect to desk.")

    async def connect(self) -> None:
        """
        Connects to the desk. Raises an exception if the connection cannot be established.
        """
        attempts = 2
        try:
            self.connection = await self.attempt_connect_n_times(attempts, 30)
            logging.info("Successfully connected to the desk.")
        except ConnectException as e:
            logging.error("Could not connect to desk after {} attempts.".format(attempts))
            raise ConnectException(
                "Could not find and connect to desk. Ensure the MAC address is correct and the desk is powered on.")


mac = 'E7:D2:6F:3E:C6:84'


async def main():
    logging.debug("Test")
    idasen = Idasen(mac)
    await idasen.connect()


os.system('python -m mypy Idasen.py')

if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(main())
    asyncio.get_event_loop().run_forever()
