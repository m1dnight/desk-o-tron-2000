import asyncio
import json

import Webserver
from Config import Config
from Desk import Desk
from Timer import Timer


def socket_to_desk(desk, cfg, timer):
    async def _handle_message(msg_json):
        print("Handling message {}".format(msg_json))
        command = msg_json["command"]
        if command == "move_up":
            asyncio.create_task(desk.move_up())
        elif command == "move_down":
            asyncio.create_task(desk.move_down())
        elif command == "stand":
            stand_height = cfg.stand()
            asyncio.create_task(desk.move_to(stand_height))
        elif command == "sit":
            sit_height = cfg.sit()
            asyncio.create_task(desk.move_to(sit_height))
        elif command == "current_height":
            height, speed = await desk.get_desk_height()
            desk_to_socket(height, speed)
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
            cfg_dict = cfg.dict()
            to_socket({'config': cfg_dict})
        else:
            print("Invalid command: {}".format(command))

    def _socket_to_desk(msg_str):
        msg_json = json.loads(msg_str)
        asyncio.create_task(_handle_message(msg_json))

    return _socket_to_desk


def to_socket(message):
    asyncio.create_task(Webserver.DeskSocketHandler.broadcast(json.dumps(message)))


def desk_to_socket(height, speed):
    message = {'current_height': height, 'speed': speed}
    to_socket(message)


def sit_task(desk, config):
    def desk_sit():
        asyncio.create_task(desk.move_to(config.sit))

    return desk_sit


async def schedule_stand_task(desk, config, timer):
    async def _move_and_schedule_next():
        print("Moving desk to stand position")
        await desk.move_to(config.stand())
        await schedule_sit_task(desk, config, timer)

    def desk_stand_task():
        asyncio.create_task(_move_and_schedule_next())

    await timer.task_after_n_seconds(config.stand_duration() * 60, desk_stand_task, "stand_task")


async def schedule_sit_task(desk, config, timer):
    async def _move_and_schedule_next():
        print("Moving desk to sit position")
        await desk.move_to(config.sit())
        await schedule_stand_task(desk, config, timer)

    def desk_sit_task():
        asyncio.create_task(_move_and_schedule_next())

    await timer.task_after_n_seconds(config.sit_duration() * 60, desk_sit_task, "sit_task")


async def main():
    config: Config = Config("configuration.yaml")
    timer: Timer = Timer()
    desk: Desk = Desk(config.mac(), desk_to_socket)
    await desk.connect_to_desk()
    await Webserver.start_webserver(config.hostname(), config.http_port(), socket_to_desk(desk, config, timer))
    await schedule_sit_task(desk, config, timer)


if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(main())
    asyncio.get_event_loop().run_forever()
