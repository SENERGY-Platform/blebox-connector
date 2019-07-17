"""
   Copyright 2019 InfAI (CC SES)

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
"""


__all__ = ('BleboxAirSensor', 'device_type_map')


from .configuration import config
import cc_lib, datetime


def mapReading(payload):
    return {
        'value': payload,
        'unit': 'µg/m³',
        'time': '{}Z'.format(datetime.datetime.utcnow().isoformat())
    }


class ReadingPM1(cc_lib.types.SensorService):
    uri = config.Senergy.st_reading_pm1
    name = "Reading pm 1"
    description = "Reading for particulate matter between 0.3 and 1 μm."

    @staticmethod
    def task(payload):
        return mapReading(payload)


class ReadingPM25(cc_lib.types.SensorService):
    uri = config.Senergy.st_reading_pm25
    name = "Reading pm 2.5"
    description = "Reading for particulate matter between 1 and 2.5 μm."

    @staticmethod
    def task(payload):
        return mapReading(payload)


class ReadingPM10(cc_lib.types.SensorService):
    uri = config.Senergy.st_reading_pm10
    name = "Reading pm 10"
    description = "Reading for particulate matter between 2.5 and 10 μm."

    @staticmethod
    def task(payload):
        return mapReading(payload)


class BleboxAirSensor(cc_lib.types.Device):
    uri = config.Senergy.dt_air_sensor
    description = "Measure different sizes of air particles."
    services = {
        "reading_pm1": ReadingPM1,
        "reading_pm2.5": ReadingPM25,
        "reading_pm10": ReadingPM10
    }

    def __init__(self, id, name, ip=None):
        self.id = id
        self.name = name
        self.ip = ip
        self.reachable = False
        self.addTag('type', "airSensor")
        self.addTag('manufacturer', "Blebox")

    def getService(self, service, *args):
        return super().getService(service).task(*args)

    def __iter__(self):
        items = (
            ("name", self.name),
            ("ip", self.ip),
            ("reachable", self.reachable)
        )
        for item in items:
            yield item


device_type_map = {
    "airSensor": BleboxAirSensor
}