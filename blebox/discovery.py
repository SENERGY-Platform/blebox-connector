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


__all__ = ('Monitor', )


from .logger import root_logger
from .device_manager import DeviceManager
from .device import device_type_map
from .configuration import config
from subprocess import call, check_output, DEVNULL
from socket import gethostbyname, getfqdn
from threading import Thread
from platform import system
from os import getenv
from requests import get, exceptions
import time, cc_lib


logger = root_logger.getChild(__name__.split(".", 1)[-1])


def ping(host) -> bool:
    return call(['ping', '-c', '2', '-t', '2', host], stdout=DEVNULL, stderr=DEVNULL) == 0


def getLocalIP() -> str:
    try:
        if config.RuntimeEnv.container:
            host_ip = getenv("HOST_IP")
            if not host_ip:
                raise Exception
            return host_ip
        else:
            sys_type = system().lower()
            if 'linux' in sys_type:
                local_ip = check_output(['hostname', '-I']).decode()
                local_ip = local_ip.replace(' ', '')
                local_ip = local_ip.replace('\n', '')
                return local_ip
            elif 'darwin' in sys_type:
                local_ip = gethostbyname(getfqdn())
                if type(local_ip) is str and local_ip.count('.') == 3:
                    return local_ip
            else:
                logger.critical("platform not supported")
                raise Exception
    except Exception as ex:
        exit("could not get local ip - {}".format(ex))


def getIpRange(local_ip) -> list:
    split_ip = local_ip.rsplit('.', 1)
    base_ip = split_ip[0] + '.'
    if len(split_ip) > 1:
        ip_range = [str(base_ip) + str(i) for i in range(2,255)]
        ip_range.remove(local_ip)
        return ip_range
    return list()


def discoverHostsWorker(ip_range, alive_hosts):
    for ip in ip_range:
        if ping(ip):
            alive_hosts.append(ip)


def discoverHosts() -> list:
    ip_range = getIpRange(getLocalIP())
    alive_hosts = list()
    workers = list()
    bin = 0
    bin_size = 3
    if ip_range:
        for i in range(int(len(ip_range) / bin_size)):
            worker = Thread(target=discoverHostsWorker, name='discoverHostsWorker', args=(ip_range[bin:bin+bin_size], alive_hosts))
            workers.append(worker)
            worker.start()
            bin = bin + bin_size
        if ip_range[bin:]:
            worker = Thread(target=discoverHostsWorker, name='discoverHostsWorker', args=(ip_range[bin:], alive_hosts))
            workers.append(worker)
            worker.start()
        for worker in workers:
            worker.join()
    return alive_hosts


class Monitor(Thread):

    def __init__(self, device_manager: DeviceManager, client: cc_lib.client.Client):
        super().__init__(name="monitor", daemon=True)
        self.__device_manager = device_manager
        self.__client = client

    def _validateHostsWorker(self, hosts, valid_hosts):
        for host in hosts:
            try:
                response = get(url="http://{}/{}".format(host, config.Api.air_sensor_device), timeout=5)
                if response.status_code == 200 and 'blebox' in response.headers.get('Server'):
                    host_info = response.json()
                    valid_hosts[host_info.get('id')] = (
                        {
                            "name": host_info.get("deviceName"),
                            "ip": host
                        },
                        {
                            "type": host_info.get("type"),
                            "reachable": True
                        }
                    )
            except exceptions.RequestException:
                pass

    def _validateHosts(self, hosts) -> dict:
        valid_hosts = dict()
        workers = list()
        bin = 0
        bin_size = 2
        if len(hosts) <= bin_size:
            worker = Thread(target=self._validateHostsWorker, name='validateHostsWorker', args=(hosts, valid_hosts))
            workers.append(worker)
            worker.start()
        else:
            for i in range(int(len(hosts) / bin_size)):
                worker = Thread(target=self._validateHostsWorker, name='validateHostsWorker',
                                args=(hosts[bin:bin + bin_size], valid_hosts))
                workers.append(worker)
                worker.start()
                bin = bin + bin_size
            if hosts[bin:]:
                worker = Thread(target=self._validateHostsWorker, name='validateHostsWorker', args=(hosts[bin:], valid_hosts))
                workers.append(worker)
                worker.start()
        for worker in workers:
            worker.join()
        return valid_hosts

    def _diff(self, known, unknown) -> tuple:
        known_set = set(known)
        unknown_set = set(unknown)
        missing = known_set - unknown_set
        new = unknown_set - known_set
        changed = {key for key in known_set & unknown_set if dict(known[key]) != unknown[key][0]}
        return missing, new, changed

    def _evaluate(self, queried_devices):
        missing_devices, new_devices, changed_devices = self._diff(self.__device_manager.devices, queried_devices)
        updated_devices = list()
        if missing_devices:
            for device_id in missing_devices:
                logger.info("can't find '{}' with id '{}'".format(
                    self.__device_manager.get(device_id).name, device_id)
                )
                try:
                    self.__client.disconnectDevice(device_id)
                    self.__device_manager.get(device_id).reachable = False
                except (cc_lib.client.DeviceDisconnectError, cc_lib.client.NotConnectedError):
                    pass
        if new_devices:
            futures = list()
            for device_id in new_devices:
                device = device_type_map[queried_devices[device_id][1]["type"]](device_id, **queried_devices[device_id][0])
                logger.info("found '{}' with id '{}'".format(device.name, device.id))
                futures.append((device, self.__client.addDevice(device, asynchronous=True)))
            for device, future in futures:
                future.wait()
                try:
                    future.result()
                    self.__device_manager.add(device, queried_devices[device.id][1]["type"])
                    self.__client.connectDevice(device, asynchronous=True)
                    device.reachable = True
                except (cc_lib.client.DeviceAddError, cc_lib.client.DeviceUpdateError):
                    pass
        if changed_devices:
            futures = list()
            for device_id in changed_devices:
                device = self.__device_manager.get(device_id)
                prev_device_name = device.name
                prev_device_reachable_state = device.reachable
                device.name = queried_devices[device_id][0]["name"]
                device.ip = queried_devices[device_id][0]["ip"]
                device.reachable = queried_devices[device_id][1]["reachable"]
                if device.reachable != prev_device_reachable_state:
                    if device.reachable:
                        self.__client.connectDevice(device, asynchronous=True)
                    else:
                        self.__client.disconnectDevice(device, asynchronous=True)
                if device.name != prev_device_name:
                    futures.append((device, prev_device_name, self.__client.updateDevice(device, asynchronous=True)))
            for device, prev_device_name, future in futures:
                future.wait()
                try:
                    future.result()
                    updated_devices.append(device.id)
                    self.__device_manager.update(device)
                except cc_lib.client.DeviceUpdateError:
                    device.name = prev_device_name
        if any((missing_devices, new_devices, updated_devices)):
            try:
                self.__client.syncHub(list(self.__device_manager.devices.values()), asynchronous=True)
            except cc_lib.client.HubError:
                pass

    def run(self):
        while True:
            unknown_devices = self._validateHosts(discoverHosts())
            self._evaluate(unknown_devices)
            time.sleep(120)
