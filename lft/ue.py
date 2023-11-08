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

from lft.perfsonar import Perfsonar
from configparser import ConfigParser
from lft.constants import *

class UE(Perfsonar):
    def __init__(self, name: str, ueConfigPath='/etc/srsran/ue.conf', buildDir='/srsRAN/build'):
        super().__init__(name)
        self.configPath = ueConfigPath
        self.config = None
        self.buildDir = buildDir

    def instantiate(self, dockerImage='alexandremitsurukaihara/lft:srsran', dockerCommand = '', dns='8.8.8.8') -> None:
        super().instantiate(dockerImage, dockerCommand, dns)
        self.config = self.readConfigFile(self.configPath)

    def start(self, deviceArgs='') -> None:
        # , transmitterIp="*", transmitterPort=2001, receiverIp="localhost", receiverPort=2000
        #args = "--rf.device_name=zmq --rf.device_args=\"tx_port=tcp://{transmitterIp}:{transmitterPort},rx_port=tcp://{receiverIp}:{receiverPort},id=ue,base_srate=23.04e6\""
        super().run(f"{self.buildDir}/srsue/src/srsue {deviceArgs} > {self.buildDir}/ue.out &")
    
    def stop(self) -> None:
        self.run(f"pkill -f -9 srsue")

    def setConfigPath(self, path: str) -> None:
        self.configPath = path

    def getConfigPath(self) -> str:
        return self.configPath

    def setConfigurationFile(self, filePath: str, destinationPath='') -> None:
        if destinationPath == '':
            destinationPath = self.configPath
        super().copyLocalToContainer(filePath, destinationPath)

    def setDeviceArgs(self, deviceArgs: str) -> None:
        self.config[RF_SECTION][DEVICE_ARGS_ATTR] = deviceArgs
        self.saveConfig(self.config, self.configPath)

    def setDeviceName(self, deviceName: str) -> None:
        self.config[RF_SECTION][DEVICE_NAME_ATTR] = deviceName
        self.saveConfig(self.config, self.configPath)

    def setTxGain(self, txGain: int) -> None:
        self.config[RF_SECTION][TX_GAIN_ATTR] = txGain
        self.saveConfig(self.config, self.configPath)

    def setRxGain(self, rxGain: int) -> None:
        self.config[RF_SECTION][RX_GAIN_ATTR] = rxGain
        self.saveConfig(self.config, self.configPath)

    def setAuthenticationAlgorithm(self, algorithmName: str) -> None:
        self.config[USIM_SECTION][ALGORITHM_ATTR] = algorithmName
        self.saveConfig(self.config, self.configPath)

    def setUEID(self, id: str) -> None:
        self.config[USIM_SECTION][IMSI_ATTR] = id
        self.saveConfig(self.config, self.configPath)
        