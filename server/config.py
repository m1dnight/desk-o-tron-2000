import yaml


class Config:
    __sit: int
    __sit_duration: int
    __stand: int
    __stand_duration: int
    __min_height: int
    __mac: str
    __max_height: int

    def __init__(self, path):
        # Read the config from disk.
        self.__path = path
        c = yaml.load(open(path, 'r'), Loader=yaml.FullLoader)

        # Populate values.
        self.__max_height = 1270
        self.__min_height = 820
        self.__sit = c['sit']
        self.__sit_duration = c['sit_duration']
        self.__stand = c['stand']
        self.__stand_duration = c['stand_duration']
        self.__mac = c['mac']

    def __generate_dict(self) -> dict:
        return {
            'sit_duration': self.__sit_duration,
            'sit': self.__sit,
            'stand': self.__stand,
            'stand_duration': self.__stand_duration,
            'mac': self.__mac
        }

    def dict(self) -> dict: 
        return self.__generate_dict()


    def write_config(self) -> None:
        yaml_cfg = self.__generate_dict()
        with open(self.__path, 'w') as file:
            yaml.dump(yaml_cfg, file)

    def update_sit(self, value: int) -> None:
        self.__sit = value
        self.write_config()


    def sit(self) -> int:
        return self.__sit

    def update_stand(self, value: int) -> None:
        self.__stand = value
        self.write_config()

    def stand(self) -> int:
        return self.__stand

    def update_sit_duration(self, value: int) -> None:
        self.__sit_duration = value
        self.write_config()

    def sit_duration(self) -> int:
        return self.__sit_duration

    def update_stand_duration(self, value: int) -> None:
        self.__stand_duration = value
        self.write_config()

    def stand_duration(self) -> int:
        return self.__stand_duration

    def update_mac(self, value: str) -> None:
        self.__mac = value
        self.write_config()

    def mac(self) -> str:
        return self.__mac
