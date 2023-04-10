# Copyright (C) 2023 Alexandre Mitsuru Kaihara
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

from node import Node
from configparser import ConfigParser

class UE(Node):
    def __init__(self, name: str, hostPath='', containerPath=''):
        super().__init__(name)
        self.defaultUEConfigPath = '/etc/srsran/ue.conf'
        self.buildDir = '/srsRAN/build'

    def instantiate(self, image='alexandremitsurukaihara/lft:srsran', dockerCommand = '', dns='8.8.8.8') -> None:
        super().instantiate(image, dockerCommand, dns)

    def start(self, transmitterIp="*", transmitterPort=2001, receiverIp="localhost", receiverPort=2000) -> None:
        super().run(f"{self.buildDir}/srsue/src/srsue --rf.device_name=zmq --rf.device_args=\"tx_port=tcp://{transmitterIp}:{transmitterPort},rx_port=tcp://{receiverIp}:{receiverPort},id=ue,base_srate=23.04e6\" > {self.buildDir}/ue.out &")
    
    def stop(self) -> None:
        super.run(f"pkill -f -9 srsue")

    def setDefaultUEConfigPath(self, path: str) -> None:
        self.defaultUEConfigPath = path

    def getdefaultUEConfigPath(self) -> str:
        return self.defaultUEConfigPath

    def setConfigurationFile(self, filePath: str, destinationPath='') -> None:
        if destinationPath == '':
            destinationPath = self.defaultUEConfigPath
        super().copyLocalToContainer(filePath, destinationPath)
