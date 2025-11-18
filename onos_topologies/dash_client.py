import subprocess
import logging
from profissa_lft.host import Host
from profissa_lft.exceptions import NodeInstantiationFailed

class DashClient(Host):
    def __init__(self, nodeName: str) -> None:
        super().__init__(nodeName)

    def instantiate(self, dockerImage="neubot/dash-client:latest", networkMode="none") -> None:
        try:
            dockerCommand = f"docker run -d --name={self.getNodeName()} --network={networkMode} --entrypoint sleep {dockerImage} infinity"
            return super().instantiate(dockerImage, dockerCommand)
        except Exception as ex:
            logging.error(f"Error instantiating DASH client {self.getNodeName()}: {str(ex)}")
            raise NodeInstantiationFailed(f"Error instantiating DASH client {self.getNodeName()}: {str(ex)}")
        
    # Brief: Executes the DASH Go binary inside the client container.
    # The command runs the compiled dash-client binary with required flags
    # and the server's IP address
    # :param server_ip: The IP address of the DASH server (e.g., 192.168.0.1)
    # :param flags: Optional flags for the dash-client binary (e.g., -y for privacy acknowledgement)
    def run_dash_test(self, server_ip: str, flags: str = "-y --ipversion 4") -> subprocess.CompletedProcess:
        command = f'bash -lc "/usr/local/bin/dash-client {flags} --server-ip {server_ip}"'
        print(f"[DASH TEST] Executing command on {self.getNodeName()}: {command}")
        return self.run(command)
    
    def setIp(self, ip: str, mask: int, interfaceName='') -> None:
        if interfaceName == '':
            interfaceName = self.getNodeName()
        self._Node__setIp(ip, mask, interfaceName)
    
