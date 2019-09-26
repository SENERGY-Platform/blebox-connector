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

__all__ = ('DeviceManager', )


from .logger import root_logger
from .device import device_type_map
from typing import Dict
from threading import Lock
from sqlite3 import connect as sqlliteConnect
from os import getcwd, path
import cc_lib


logger = root_logger.getChild(__name__.split(".", 1)[-1])


class DeviceManager:

    def __init__(self):
        self.__device_pool = dict()
        self.__lock = Lock()
        self.__db_path = path.join(getcwd(),"storage/devices.sqlite3")
        with sqlliteConnect(self.__db_path) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS devices (id TEXT PRIMARY KEY UNIQUE, name TEXT, type TEXT)")
        conn.close()
        self.__loadFromDB()

    def add(self, device: cc_lib.types.Device, d_type) -> None:
        if not isinstance(device, cc_lib.types.Device):
            raise TypeError
        self.__lock.acquire()
        if device.id not in self.__device_pool:
            self.__device_pool[device.id] = device
            with sqlliteConnect(self.__db_path) as conn:
                conn.execute("INSERT INTO devices (id, name, type) VALUES (?, ?, ?)", (device.id, device.name, d_type))
            conn.close()
        else:
            logger.warning("device '{}' already in pool".format(device.id))
        self.__lock.release()

    def delete(self, device_id: str) -> None:
        if not isinstance(device_id, str):
            raise TypeError
        self.__lock.acquire()
        try:
            del self.__device_pool[device_id]
            with sqlliteConnect(self.__db_path) as conn:
                conn.execute("DELETE FROM devices WHERE id=(?)", (device_id,))
            conn.close()
        except KeyError:
            logger.warning("device '{}' does not exist in device pool".format(device_id))
        self.__lock.release()

    def get(self, device_id: str) -> cc_lib.types.Device:
        if not isinstance(device_id, str):
            raise TypeError
        self.__lock.acquire()
        try:
            device = self.__device_pool[device_id]
        except KeyError:
            logger.error("device '{}' not in pool".format(device_id))
            self.__lock.release()
            raise
        self.__lock.release()
        return device

    def update(self, device: cc_lib.types.Device):
        if not isinstance(device, cc_lib.types.Device):
            raise TypeError
        with sqlliteConnect(self.__db_path) as conn:
            conn.execute("UPDATE devices SET name=(?) WHERE id=(?)", (device.name, device.id))
        conn.close()

    def clear(self) -> None:
        self.__lock.acquire()
        self.__device_pool.clear()
        with sqlliteConnect(self.__db_path) as conn:
            conn.execute("DROP TABLE IF EXISTS devices")
            conn.execute("CREATE TABLE IF NOT EXISTS devices (id TEXT PRIMARY KEY UNIQUE, name TEXT, type TEXT)")
        conn.close()
        self.__lock.release()

    @property
    def devices(self) -> Dict[str, cc_lib.types.Device]:
        self.__lock.acquire()
        devices = self.__device_pool.copy()
        self.__lock.release()
        return devices

    def __loadFromDB(self):
        with sqlliteConnect(self.__db_path) as conn:
            for id, name, type in conn.execute("SELECT * FROM devices"):
                self.__device_pool[id] = device_type_map[type](id, name)
        conn.close()
