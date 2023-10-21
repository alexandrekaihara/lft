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

from lft.node import Node
from configparser import ConfigParser

class EPC(Node):
    def __init__(self, name: str):
        super().__init__(name)
        self.defaultEPCConfigPath = '/etc/srsran/epc.conf'
        self.defaultEPCUserDbPath = '/etc/srsran/user_db.csv'
        self.buildDir = "/srsRAN/build"

    def instantiate(self, dockerImage='alexandremitsurukaihara/lft:srsran') -> None:
        super().instantiate(dockerImage)

    def start(self) -> None:
        self.run(f"{self.buildDir}/srsepc/src/srsepc > {self.buildDir}/epc.out &")

    def stop(self) -> None:
        self.run("pkill -f -9 srsepc")

    def setDefaultEPCConfigPath(self, path: str) -> None:
        self.defaultEPCConfigPath = path

    def getDefaultEPCConfigPath(self) -> str:
        return self.defaultEPCConfigPath

    def setConfigurationFile(self, filePath, destinationPath='') -> None:
        if destinationPath == '':
            destinationPath = self.defaultEPCConfigPath
        self.copyLocalToContainer(filePath, destinationPath)

    def setEPCAddress(self, ip='127.0.1.100', epcConfigPath='') -> None:
        if epcConfigPath == '':
            epcConfigPath = self.defaultEPCConfigPath
        self.run(f"sed -i \'s/^mme_bind_addr.* =.*/mme_bind_addr = {ip}/\' {epcConfigPath}")
        self.run(f"sed -i \'s/^gtpu_bind_addr.* =.*/gtpu_bind_addr = {ip}/\' {epcConfigPath}")
        
    def setSgiInterfaceAddress(self, ip='172.16.0.1', epcConfigPath='') -> None:
        if epcConfigPath == '':
            epcConfigPath = self.defaultEPCConfigPath
        self.run(f"sed -i \'s/^sgi_if_addr =.*/sgi_if_addr = {ip}/\' {epcConfigPath}")

    # Each UE ID must be unique and must be set in "imsi" parameter located inside the ue.conf
    def addNewUE(self, name: str, ID: str, IP="dynamic", configFilePath='') -> None:
        if configFilePath == '':
            configFilePath = self.defaultEPCUserDbPath
        self.run(f"echo \'{name},mil,{ID},00112233445566778899aabbccddeeff,opc,63bfa50ee6523365ff14c1f45f88737d,9001,000000001234,7,{IP}\' >> {configFilePath}")

    