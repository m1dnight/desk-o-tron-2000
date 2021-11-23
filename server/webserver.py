import asyncio
import json
import idasenx
import config
import bleak
import websockets


def log_info(*args):
    print(*args)


def log_err(*args):
    print(*args)


################################################################################
# Constants                                                                    #
################################################################################

PORT = 8000
ADDRESS = "0.0.0.0"
CFG="config.yaml"

connection = None
desk : bleak.BleakClient
desk = None 

################################################################################
# Others                                                                       #
################################################################################

# noinspection PyUnresolvedReferences
async def send_incoming(msg):
    global connection
    if connection is not None:
        log_info("<<< {}".format(msg))
        payload = json.dumps(msg)
        await connection.send(payload)


async def handle_message(msg_str: str, cfg: config.Config):
    global desk 
    log_info(">>> " + msg_str)
    msg_json = json.loads(msg_str)

    command = msg_json["command"]

    if command == "move_up":
        asyncio.create_task(idasenx.move_up(desk))
    elif command == "move_down":
        asyncio.create_task(idasenx.move_down(desk))
    elif command == "stand":
        stand_height = cfg.stand()
        asyncio.create_task(idasenx.move_to_target(desk, stand_height))
    elif command == "sit":
        sit_height = cfg.sit()
        asyncio.create_task(idasenx.move_to_target(desk, sit_height))
    elif command == "current_height":
        height, speed = await idasenx.current_height(desk)
        notify_height_change(height, speed)
    elif command == "set_sit":
        value = msg_json["value"]
        cfg.update_sit(value)
    elif command == "set_stand":
        value = msg_json["value"]
        cfg.update_stand(value)
    elif command == "set_sit_duration":
        value = msg_json["value"]
        cfg.update_sit_duration(value)
    elif command == "set_stand_duration":
        value = msg_json["value"]
        cfg.update_stand_duration(value)
    elif command == "get_config": 
        dict = cfg.dict()

        asyncio.create_task(send_incoming({'config': dict}))
    else:
        log_err("Invalid command: {}".format(msg_str))


def notify_height_change(current_height_mm, _speed_mm_s):
    global connection
    payload = {"current_height": current_height_mm}
    if connection is not None:
        asyncio.create_task(send_incoming(payload))


def server_loop(desk, cfg):
    async def _server_loop(sock):
        global connection
        log_info("🌎 Starting webserver..")
        print(desk)
        connection = sock
        asyncio.create_task(idasenx.add_callback(idasenx.UUID_HEIGHT, notify_height_change))
        try:
            while True:
                command = await connection.recv()
                asyncio.create_task(handle_message(command, cfg))
        except websockets.ConnectionClosedOK:
            log_info("🔌 Client disconnected")
            pass

    return _server_loop


async def connect_to_desk():
    global desk
    desk = await idasenx.start_desk_daemon()



async def heartbeat(): 
    global desk 
    # Sleep for 10 seconds. 
    await asyncio.sleep(10)


    if desk.is_connected: 
        print("Connected")
    else: 
        print("Disconnected")
        asyncio.create_task(connect_to_desk())

    asyncio.create_task(heartbeat())

async def start_server():
    try:
        global desk
        desk = await idasenx.start_desk_daemon()
        cfg = config.Config(CFG)
        asyncio.create_task(heartbeat())
        await websockets.serve(server_loop(desk, cfg), ADDRESS, PORT)
    except KeyboardInterrupt:
        await desk.disconnect()  


try:
    asyncio.get_event_loop().run_until_complete(start_server())
    asyncio.get_event_loop().run_forever()
except bleak.BleakError as e:
    print("💻 Bluetooth connection error")
    print(e)  

