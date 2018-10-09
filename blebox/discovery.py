"""
   Copyright 2018 SEPL Team

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
    from connector_client.modules.http_lib import Methods as http
    from connector_client.modules.device_pool import DevicePool
    from connector_client.client import Client
    from blebox.logger import root_logger
    from blebox.device import BleboxDevice
except ImportError as ex:
    exit("{} - {}".format(__name__, ex.msg))
from subprocess import call, check_output, DEVNULL
from socket import gethostbyname, getfqdn
from threading import Thread
from platform import system
import time, json

logger = root_logger.getChild(__name__)


def ping(host) -> bool:
    return call(['ping', '-c', '1', '-t', '2', host], stdout=DEVNULL, stderr=DEVNULL) == 0

def getLocalIP() -> str:
    sys_type = system().lower()
    try:
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
    return str()

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
    _known_devices = dict()

    def __init__(self):
        super().__init__()
        unknown_devices = self._validateHosts(discoverHosts())
        self._evaluate(unknown_devices, True)
        self.start()

    def _validateHostsWorker(self, hosts, valid_hosts):
        for host in hosts:
            response = http.get('http://{}/api/device/state'.format(host), timeout=3)
            if response.status == 200 and 'blebox' in response.header.get('Server'):
                host_info = json.loads(response.body)
                valid_hosts[host_info.get('id')] = host_info

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
        changed = {k for k in known_set & unknown_set if known[k] != unknown[k]}
        return missing, new, changed

    def _evaluate(self, unknown_devices, init):
        missing_devices, new_devices, changed_devices = self._diff(__class__._known_devices, unknown_devices)
        if missing_devices:
            for missing_device_id in missing_devices:
                logger.info("can't find '{}' with id '{}'".format(__class__._known_devices[missing_device_id].get('deviceName'), missing_device_id))
                if init:
                    DevicePool.remove(missing_device_id)
                else:
                    Client.disconnect(missing_device_id)
        if new_devices:
            for new_device_id in new_devices:
                name = unknown_devices[new_device_id].get('deviceName')
                logger.info("found '{}' with id '{}'".format(name, new_device_id))
                device = BleboxDevice(new_device_id, 'iot#b9baa8e6-7955-4dd9-9bdf-3885f3bfbf12', name, unknown_devices[new_device_id].get('ip'))
                device.addTag('type', unknown_devices[new_device_id].get('type'))
                if init:
                    DevicePool.add(device)
                else:
                    Client.add(device)
        if changed_devices:
            for changed_device_id in changed_devices:
                device = DevicePool.get(changed_device_id)
                name = unknown_devices[changed_device_id].get('deviceName')
                if not name == device.name:
                    device.name = name
                    if init:
                        DevicePool.update(device)
                    else:
                        Client.update(device)
                    logger.info("name of '{}' changed to {}".format(changed_device_id, name))
        __class__._known_devices = unknown_devices

    def run(self):
        while True:
            time.sleep(120)
            unknown_devices = self._validateHosts(discoverHosts())
            self._evaluate(unknown_devices, False)