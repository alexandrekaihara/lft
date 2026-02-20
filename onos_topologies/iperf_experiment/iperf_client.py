import subprocess
import logging
from profissa_lft.host import Host
from profissa_lft.exceptions import NodeInstantiationFailed

class IperfClient(Host):
    def __init__(self, nodeName: str) -> None:
        super().__init__(nodeName)

    def instantiate(self, dockerImage="lft-iperf:latest", networkMode="none", mapPorts=False) -> None:
        try:
            dockerCommand = f"docker run -d --name={self.getNodeName()} --network={networkMode} --cap-add=NET_ADMIN --entrypoint sleep {dockerImage} infinity"
            return super().instantiate(dockerImage, dockerCommand)
        except Exception as ex:
            logging.error(f"Error instantiating IPERF client {self.getNodeName()}: {str(ex)}")
            raise NodeInstantiationFailed(f"Error instantiating IPERF client {self.getNodeName()}: {str(ex)}")
        
    def setIp(self, ip: str, mask: int, interfaceName='') -> None:
        if interfaceName == '':
            interfaceName = self.getNodeName()
        self._Node__setIp(ip, mask, interfaceName)
    
