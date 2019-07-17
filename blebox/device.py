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


__all__ = ()


from .logger import root_logger
from cc_lib.device import Device

logger = root_logger.getChild(__name__)


class BleboxDevice(Device):
    def __init__(self, id, type, name, ip):
        super().__init__(id, type, name)
        self.ip = ip
        self.addTag('manufacturer', 'Blebox')
