# Copyright (C) 2025 Alexandre Mitsuru Kaihara
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


from .switch import Switch


class SwitchMeter(Switch):
    # Brief: Instantiate a switch class, where it can be defined to capture flow data of each interface added
    # Params:
    # Return:
    #   None
    def __init__(self, name: str, hostPath='', containerPath=''):
        super().__init__(name, hostPath, containerPath)

    # Brief: Instantiate an OpenvSwitch switch container
    # Params:
    # Return:
    #   None
    def instantiate(self, image='alexandremitsurukaihara/lft:openvswitchmeter', controllerIP='', controllerPort=-1) -> None:
        super().instantiate(image=image, controllerIP=controllerIP, controllerPort=controllerPort)

    # Brief: Start packet capture using TCPDUMP and process with CICFlowMeter to generate flow-based features.
    # Params:
    #   str interfaceName: Name of the network interface that exists in the current container to capture packets from
    #   str outputPath: Directory where the output files inside the container (pcap data) will be saved
    #   int rotateInterval: Time interval in seconds to rotate the pcap files (default: 60)
    # Return: None
    def collectPacketsCICFlowMeter(self, interfaceName: str, outputPath: str, rotateInterval=60) -> None:
        self.run(f"./TCPDUMP_and_CICFlowMeter-master/capture_interface_pcap.sh {interfaceName} {outputPath} {rotateInterval}")

    # Brief: Set up the tshark to sniff all the packets into pcap files
    # Params:
    #   List<Node> nodes: References of the nodes connected to this switch to sniff packets
    #   boolean sniffAll: If sniff all is set  
    # Return:
    def convertPcapIntoFlows(self, pcapPath: str, destPath) -> None:
        self.run(f'./TCPDUMP_and_CICFlowMeter-master/convert_pcap_csv.sh {pcapPath}')
        self.run('find /TCPDUMP_and_CICFlowMeter-master/csv -type f -exec mv {}' + f' {destPath} \\;')
