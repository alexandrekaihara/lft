from .node import Node
from json import load, dump


class Perfsonar(Node):
    def instantiate(self, dockerImage='alexandremitsurukaihara/lft:srsran', dockerCommand = '', dns='8.8.8.8', runCommand='', cpus='', memory='') -> None:
        super().instantiate(dockerImage=dockerImage, dockerCommand=dockerCommand, dns=dns, runCommand=runCommand, cpus=cpus, memory=memory)

    def readLimitFile(self, limitPath="/etc/pscheduler/limits.conf"):
        randomTmpName = self.getHashFromString(limitPath) 
        self.copyContainerToLocal(limitPath, f"/tmp/lft/{randomTmpName}")

        with open(f"/tmp/lft/{randomTmpName}") as f:
            self.limitData = load(f)

    def saveLimitFile(self, limitPath="/etc/pscheduler/limits.conf"):
        randomTmpName = self.getHashFromString(limitPath)
        with open(f"/tmp/lft/{randomTmpName}", "w") as f:
            dump(self.limitData, f)
        self.copyLocalToContainer(f"/tmp/lft/{randomTmpName}", limitPath)

    def addRouteException(self, ip: str, netmask: int) -> None:
        self.limitData['identifiers'][2]['data']['exclude'].append(f"{ip}/{netmask}")

