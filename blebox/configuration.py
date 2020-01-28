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

__all__ = ('config', )


from simple_conf import configuration, section
from os import getcwd, makedirs
from os.path import exists as path_exists

user_dir = '{}/storage'.format(getcwd())

@configuration
class BleboxConf:

    @section
    class RuntimeEnv:
        container = False
        max_start_delay = 30

    @section
    class Api:
        air_sensor_state = None
        air_sensor_device = None

    @section
    class Senergy:
        dt_air_sensor = None

    @section
    class Logger:
        level = "info"


if not path_exists(user_dir):
    makedirs(user_dir)

config = BleboxConf('blebox.conf', user_dir)


if not all((config.Senergy.dt_air_sensor, )):
    exit('Please provide a SENERGY device and service types')
