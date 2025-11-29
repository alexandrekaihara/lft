import os
from pathlib import Path
import logging
from profissa_lft.host import Host
from profissa_lft.exceptions import NodeInstantiationFailed

class DashServer(Host):
    def __init__(self, nodeName: str) -> None:
        super().__init__(nodeName)

    def instantiate(self, dockerImage="neubot/dash:latest", mapPorts=True) -> None:
        try:
            curr_dir = Path(__file__).resolve().parent
            certs_dir = (curr_dir / "certs").resolve()

            # Host datadir root (single source of truth)
            host_datadir_root = Path(os.environ.get("LFT_DATADIR", str(curr_dir))).resolve() / "datadir"
            host_datadir_root.mkdir(parents=True, exist_ok=True)

            base_command = (
                f"-v {certs_dir}:/certs:ro "
                f"-v {host_datadir_root}:/datadir "
                f"{dockerImage} "
                f"-datadir /datadir "
                f"-http-listen-address :80 "
                f"-https-listen-address '' "
                f"-prometheusx.listen-address :9999 "
                f"-tls-cert /certs/cert.pem -tls-key /certs/key.pem"
            )

            if mapPorts:
                dockerCommand = f"docker run -d --name={self.getNodeName()} --network=bridge -p 80:80 -p 9990:9999 {base_command}"
            else:
                dockerCommand = f"docker run -d --name={self.getNodeName()} --network=none {base_command}"

            return super().instantiate(dockerImage, dockerCommand)

        except Exception as ex:
            logging.error(f"Error instantiating DASH server {self.getNodeName()}: {str(ex)}")
            raise NodeInstantiationFailed(f"Error instantiating DASH server {self.getNodeName()}: {str(ex)}")
        
    def setIp(self, ip: str, mask: int, interfaceName='') -> None:
        if interfaceName == '':
            interfaceName = self.getNodeName()
        self._Node__setIp(ip, mask, interfaceName)
