#from os import getcwd

from node import Node

class Atomix(Node):
    def instantiate(self, hostConfPath, containerConfPath='/etc/atomix/conf'):
        command = f"docker run -it -v {hostConfPath}:{containerConfPath} -name={self.getNodeName()} atomix/atomix:3.1.12 --config {containerConfPath}/atomix.conf --ignore-resources"
        super().instantiate(dockerImage='atomix/atomix:3.1.12', dockerCommand=command)
        