import asyncio
import struct
# from bleak import BleakScanner
from bleak import BleakClient


# At the absolute bottom the desk is 62,5cm high at the top of the table.
# At the absolute top the dsk is 1270cm high at the top of the table.
# So when the desk tells us its at 0.0, the desk is actually 62cm high.

def log_info(*args):
    print(*args)


address = "E7:D2:6F:3E:C6:84"

stand_height = 128
sit_height = 89


# Notes:
#  - The height from the GATT event is in meter * 10^-4, so we have to divide it by
#    10 to get mm. Apparently this used to be called dimimeter (http://www.ibiblio.org/units/prefixes.html).


def raw_to_millimeter(raw: float) -> float:
    return raw / 10


def millimeter_to_raw(millimeter: float) -> float:
    return millimeter * 10


def raw_to_millimeter_per_second(raw: float) -> float:
    return raw / 100


def human_to_machine_height(millimeter: float) -> float:
    return millimeter - 620

def machine_to_human_height(millimeter: float) -> float:
    return millimeter + 620


################################################################################
# Constants                                                                    #
################################################################################

UP = 1
DOWN = 0
# GATT Codes
UUID_HEIGHT = "99fa0021-338a-1024-8a49-009c0215f78a"
UUID_COMMAND = "99fa0002-338a-1024-8a49-009c0215f78a"
UUID_REFERENCE_INPUT = "99fa0031-338a-1024-8a49-009c0215f78a"

COMMAND_UP = bytearray(struct.pack("<H", 71))
COMMAND_DOWN = bytearray(struct.pack("<H", 70))
COMMAND_STOP = bytearray(struct.pack("<H", 255))

################################################################################
# Example Callbacks                                                            #
################################################################################
callbacks = {UUID_HEIGHT: set()}


async def add_callback(uuid, func):
    global callbacks
    callbacks[uuid].add(func)
    return None


async def remove_callback(uuid, func):
    global callbacks
    callbacks[uuid].remove(func)
    return None


def height_changed(_sender: int, data: bytearray):
    current_height_mm, speed_mm_s = unpack_move_data(data)
    for cb in callbacks[UUID_HEIGHT]:
        cb(current_height_mm, speed_mm_s)


def unpack_move_data(data: bytearray):
    height_raw, speed = struct.unpack("<Hh", data)
    current_height_mm = raw_to_millimeter(height_raw)
    speed_mm_s = raw_to_millimeter_per_second(speed)
    return current_height_mm, speed_mm_s


def height_change_log(current_height_mm, speed_mm_s):
    log_info("Desk moved to {}mm @ {}mm/s".format(current_height_mm, speed_mm_s))


async def move_up(client: BleakClient):
    asyncio.create_task(client.write_gatt_char(UUID_COMMAND, COMMAND_UP))


async def move_down(client: BleakClient):
    asyncio.create_task(client.write_gatt_char(UUID_COMMAND, COMMAND_DOWN))


async def current_height(client: BleakClient): 
    print(client.is_connected)
    return unpack_move_data(await client.read_gatt_char(UUID_HEIGHT))


async def move_to_target(client: BleakClient, target: int):
    start_height, start_speed = unpack_move_data(await client.read_gatt_char(UUID_HEIGHT))

    # Depending on the target and the current height the direction is determined.
    direction = DOWN if target < start_height else UP
    command = COMMAND_DOWN if direction == DOWN else COMMAND_UP

    log_info("Moving desk {} to {}mm. Currently at {}mm.".format("down" if direction == DOWN else "up", target,
                                                                 start_height))
    # Create a future to resolve when the move has completed.
    move_done = asyncio.get_event_loop().create_future()

    # The _move callback is called whenever the height changes.
    # Every invocation the current height is checked.
    # If the threshold is reached, resolve the future.
    # Otherwise, schedule a task every 6 updates.
    # 6 is a magic number.
    update_counter = 0

    def _move(current_height_mm: float, speed_mm_s: float):
        nonlocal update_counter
        nonlocal command
        update_counter = update_counter + 1
        log_info("Desk moved to {}mm @ {}mm/s".format(current_height_mm, speed_mm_s))

        # If the desk moved (speed was not 0.0) it must be
        # checked to see if it is at the right height.
        # If it's not at the right height yet, only send another command
        # if the desk sent around 6 updates.
        if abs(current_height_mm - target) <= 2:
            log_info("Reached target height.")
            asyncio.create_task(remove_callback(UUID_HEIGHT, _move))
            move_done.set_result(True)

        # When the speed of the desk is 0.0, one of two things happened.
        # The desk is at the end or beginning, which is fine, but we have to stop.
        # The desk is being pushed on, so it can't go up enough, so we have to stop.
        # Stopping means resolving the future so move_to_target can return.
        elif speed_mm_s == 0:
            log_info("Desk slowed down. Halting move.")
            asyncio.create_task(remove_callback(UUID_HEIGHT, _move))
            move_done.set_result(True)


        elif update_counter % 6 == 0:
            asyncio.create_task(client.write_gatt_char(UUID_COMMAND, command))

    # Allow a margin of 5mm to avoid oscillating.
    if abs(target - start_height) <= 1:
        return None
    else:
        log_info("Current height {}mm. Target is {}mm. Moving up at {}mm/s.".format(start_height, target, start_speed))

        # Register a callback for when the height changes.
        # The callback will keep rescheduling move tasks on the desk until it either stops, or until it reached the
        # right height.
        asyncio.create_task(add_callback(UUID_HEIGHT, _move))

        # Make the desk move up once.
        asyncio.create_task(client.write_gatt_char(UUID_COMMAND, command))

        try:
            await asyncio.wait_for(move_done, timeout=30)
        except asyncio.TimeoutError as _e:
            log_info('Desk move did not complete within reasonable time.')
            asyncio.create_task(remove_callback(UUID_HEIGHT, _move))


def disconnected(client): 
    print("Client disconnected! Callback!")


async def desk_daemon(mac_address: str) -> BleakClient:
    client = BleakClient(mac_address, disconnect_callback=disconnected)
    await client.connect()
    log_info("Connected to desk.")

    # Setup all the callbacks.
    await client.start_notify(UUID_HEIGHT, height_changed)
    asyncio.create_task(add_callback(UUID_HEIGHT, height_change_log))

    return client


async def start_desk_daemon():
    return await desk_daemon(address)
