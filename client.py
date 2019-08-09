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


from blebox import Monitor, root_logger, DeviceManager, config
from requests import get, exceptions
from time import sleep
import json, time, cc_lib


logger = root_logger.getChild(__name__)


device_manager = DeviceManager()


def on_connect(client: cc_lib.client.Client):
    devices = device_manager.devices
    for device in devices.values():
        try:
            if device.reachable:
                client.connectDevice(device, asynchronous=True)
        except cc_lib.client.DeviceConnectError:
            pass


client_connector = cc_lib.client.Client()
client_connector.setConnectClbk(on_connect)

device_monitor = Monitor(device_manager, client_connector)


def pushReadings():
    msg = cc_lib.client.message.Message(str())
    while True:
        for device in device_manager.devices.values():
            if device.reachable:
                try:
                    response = get(url="http://{}/{}".format(device.ip, config.Api.air_sensor_state))
                    if response.status_code == 200:
                        air_state = response.json()
                        for sensor in air_state['air']['sensors']:
                            msg.data = json.dumps(device.getService("reading_{}".format(sensor['type']), sensor['value']))
                            client_connector.emmitEvent(
                                cc_lib.client.message.EventEnvelope(device, "reading_{}".format(sensor['type']), msg),
                                asynchronous=True
                            )
                except exceptions.RequestException:
                    logger.error("could not send request to '{}'".format(device.ip))
                except Exception as ex:
                    logger.error(ex)
        time.sleep(300)


if __name__ == '__main__':
    while True:
        try:
            client_connector.initHub()
            break
        except cc_lib.client.HubInitializationError:
            sleep(10)
    client_connector.connect(reconnect=True)
    device_monitor.start()
    pushReadings()
