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

class EnB(Node):
    def __init__(self, name: str, hostPath='', containerPath=''):
        super().__init__(name)
        self.defaultEnBConfigPath = '/etc/srsran/enb.conf'
        self.buildDir = '/srsRAN/build'

    def instantiate(self, image='alexandremitsurukaihara/lft:srsran', dockerCommand = '', dns='8.8.8.8') -> None:
        super().instantiate(image, dockerCommand, dns)

    def start(self, transmitterIp="*", transmitterPort=2000, receiverIp="localhost", receiverPort=2001) -> None:
        super().run(f"{self.buildDir}/srsenb/src/srsenb --rf.device_name=zmq --rf.device_args=\'fail_on_disconnect=true,tx_port=tcp://{transmitterIp}:{transmitterPort},rx_port=tcp://{receiverIp}:{receiverPort},id=enb,base_srate=23.04e6\' > {self.buildDir}/enb.out &")
    
    def stop(self) -> None:
        super().run("pkill -f -9 srsenb")

    def setDefaultEnBConfigPath(self, path: str) -> None:
        self.defaultEnBConfigPath = path

    def getdefaultEnBConfigPath(self) -> None:
        return self.defaultEnBConfigPath

    def setConfigurationFile(self, filePath: str, destinationPath='') -> None:
        if destinationPath == '':
            destinationPath = self.defaultEnBConfigPath
        super().copyLocalToContainer(filePath, destinationPath)

    def setEPCAddress(self, ip: str, enbConfigPath='') -> None:
        if enbConfigPath == '':
            enbConfigPath = self.defaultEnBConfigPath
        super().run(f"sed -i \'s/^mme_addr.* =.*/mme_addr = {ip}/\' {enbConfigPath}")
        
    def setEnBAddress(self, ip: str, enbConfigPath='') -> None:
        if enbConfigPath == '':
            enbConfigPath = self.defaultEnBConfigPath
        
        super().run(f"sed -i \'s/^gtp_bind_addr.* =.*/gtp_bind_addr = {ip}/\' {enbConfigPath}")
        super().run(f"sed -i \'s/^s1c_bind_addr.* =.*/s1c_bind_addr = {ip}/\' {enbConfigPath}")
        
