# Copyright (C) 2022 Alexandre Mitsuru Kaihara
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

from .node import Node
from .exceptions import NodeInstantiationFailed


class CICFlowMeter(Node): 
    # Brief: Instantiate a CICFlowMeter class, where it can be defined to capture flow data of each interface added
    # Params:
    # Return:
    #   None
    def __init__(self, name: str, hostPath='', containerPath=''):
        super().__init__(name)
        self.__mount = False
        if hostPath != '' and containerPath != '':
            self.__hostPath = hostPath
            self.__containerPath = containerPath
            self.__mount = True
        else: 
            raise Exception(f"Invalid hostPath and containerPath mount point on {self.getNodeName()}. hostPath and containerPath cannot be null")

    # Brief: Instantiate an OpenvSwitch switch container
    # Params:
    # Return:
    #   None
    def instantiate(self, image='alexandremitsurukaihara/lst2.0:cicflowmeter') -> None:
        mount = ''
        if self.__mount: mount = f'-v {self.__hostPath}:{self.__containerPath}'
        super().instantiate(dockerCommand=f"docker run -d --network=none --privileged {mount} --name={self.getNodeName()} {image}")
        
    # Brief: Convert pcaps into csv of flows
    # Params:
    #   pcapPath: Container path that contains all the pcap files
    #   destPath: 
    # Return:
    def convertPcapIntoFlows(self, pcapPath: str, destPath) -> None:
        self.run(f'./TCPDUMP_and_CICFlowMeter-master/convert_pcap_csv.sh {pcapPath}')
        self.run('find /TCPDUMP_and_CICFlowMeter-master/csv -type f -exec mv {}' + f' {destPath} \\;')