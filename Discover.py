from bleak import BleakScanner


class Discovery:

    @staticmethod
    async def discover_desks():
        discovered = await BleakScanner.discover()
        return [x for x in discovered if x.name != None and "Desk" in x.name]
