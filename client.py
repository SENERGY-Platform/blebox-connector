"""
   Copyright 2018 InfAI (CC SES)

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

try:
    from connector_lib.modules.http_lib import Methods as http
    from connector_lib.modules.device_pool import DevicePool
    from connector_lib.client import Client
    from blebox.discovery import Monitor
    from blebox.logger import root_logger
except ImportError as ex:
    exit("{} - {}".format(__name__, ex.msg))
from threading import Thread
import json, time, datetime


logger = root_logger.getChild(__name__)


def pushReadings():
    while True:
        for device in DevicePool.devices().values():
            try:
                #response = http.get('http://{}/api/air/kick'.format(device.ip))
                #if response.status == 204:
                #    time.sleep(5)
                response = http.get('http://{}/api/air/state'.format(device.ip))
                if response.status == 200:
                    air_state = json.loads(response.body)
                    for sensor in air_state['air']['sensors']:
                        Client.event(
                            device.id,
                            'reading_{}'.format(sensor['type']),
                            json.dumps({
                                'value': sensor['value'],
                                'unit': 'µg/m³',
                                'time': '{}Z'.format(datetime.datetime.utcnow().isoformat())
                            }),
                            block=False
                        )
            except Exception as ex:
                logger.error(ex)
        time.sleep(300)

readings_scraper = Thread(target=pushReadings, name="Scraper")


if __name__ == '__main__':
    device_monitor = Monitor()
    connector_client = Client(device_manager=DevicePool)
    readings_scraper.start()
