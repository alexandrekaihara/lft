import logging
import subprocess
from profissa_lft.node import Node
from profissa_lft.exceptions import NodeInstantiationFailed

class Router(Node):
    # Brief: Instantiate a router class using Quagga for OSPF/L3 routing
    # Params:
    #   String name: Name of the router container
    #   String hostPath: Path on the host machine to bind-mount
    #   String containerPath: Path inside the container for the bind-mount
    # Return:
    #   None
    def __init__(self, name: str, hostPath='', containerPath=''):
        super().__init__(name)
        if hostPath == '' and containerPath == '':
            self.__mount = False
        elif hostPath != '' and containerPath != '':
            self.__hostPath = hostPath
            self.__containerPath = containerPath
            self.__mount = True
        else: 
            raise Exception(f"Invalid hostPath and containerPath mount point on {self.getNodeName()}. hostPath and containerPath cannot be null")

    # Brief: Instantiate a Quagga router container
    # Params:
    #   String image: Docker image to run the router
    #   String networkMode: Docker network mode (e.g., 'bridge', 'none')
    # Return:
    #   None
    def instantiate(self, image="quagga", networkMode="none", **kwargs) -> None:
        mount = ''
        if self.__mount: mount = f'-v {self.__hostPath}:{self.__containerPath}'
        
        cmd = f"docker run -d --privileged --cap-add=NET_ADMIN --sysctl net.ipv4.ip_forward=1 --network={networkMode} {mount} --name={self.getNodeName()} {image}"
        try:
            super().instantiate(dockerCommand=cmd)
        except Exception as ex:
            logging.error(f"Error while creating the router {self.getNodeName()}: {str(ex)}")
            raise NodeInstantiationFailed(f"Error while creating the router {self.getNodeName()}: {str(ex)}")
        
    # Brief: Connect this router to another node via a veth pair
    # Params:
    #   Node other_node: Reference to the node it will connect to
    #   String if1: Interface name on this router
    #   String if2: Interface name on the peer node
    # Return:
    #   None
    def connect(self, other_node, if1: str, if2: str) -> None:
        try:
            name1 = self.getNodeName()
            name2 = other_node.getNodeName()
            
            subprocess.run(f"sudo ip link delete {if1} 2>/dev/null || true", shell=True)
            subprocess.run(f"sudo ip link delete {if2} 2>/dev/null || true", shell=True)

            pid1 = subprocess.check_output(f"docker inspect -f '{{{{.State.Pid}}}}' {name1}", shell=True, text=True).strip()
            pid2 = subprocess.check_output(f"docker inspect -f '{{{{.State.Pid}}}}' {name2}", shell=True, text=True).strip()

            symlink_cmd = (
                f"sudo mkdir -p /var/run/netns && "
                f"sudo ln -sf /proc/{pid1}/ns/net /var/run/netns/{name1} && "
                f"sudo ln -sf /proc/{pid2}/ns/net /var/run/netns/{name2}"
            )
            subprocess.run(symlink_cmd, shell=True, check=True, stdout=subprocess.DEVNULL)

            cmd = (
                f"sudo ip link add {if1} type veth peer name {if2} && "
                f"sudo ip link set {if1} netns {name1} && "
                f"sudo ip link set {if2} netns {name2} && "
                f"sudo docker exec {name1} ip link set {if1} up && "
                f"sudo docker exec {name2} ip link set {if2} up"
            )
            subprocess.run(cmd, shell=True, check=True, stdout=subprocess.DEVNULL)

        except Exception as ex:
            logging.error(f"Error connecting router {self.getNodeName()} to {other_node.getNodeName()}: {str(ex)}")
            raise Exception(f"Error connecting router {self.getNodeName()} to {other_node.getNodeName()}: {str(ex)}")

    # Brief: Set traffic control (TC) properties on a specific interface
    # Params:
    #   String interfaceName: Interface to apply the traffic control
    #   String throughput: Rate limit (e.g., '100mbit')
    #   String delay: Added delay (e.g., '10ms')
    #   String jitter: Added jitter (e.g., '2ms')
    # Return:
    #   None
    def setInterfaceProperties(self, interfaceName: str, throughput: str, delay: str, jitter: str) -> None:
        cmd = f"docker exec {self.getNodeName()} tc qdisc replace dev {interfaceName} root netem delay {delay} rate {throughput}"
        try:
            subprocess.run(cmd, shell=True, check=True, stdout=subprocess.DEVNULL)
        except Exception as ex:
            logging.error(f"Error setting interface properties on {self.getNodeName()} ({interfaceName}): {str(ex)}")
            raise Exception(f"Error setting interface properties on {self.getNodeName()} ({interfaceName}): {str(ex)}")

    # Brief: Run a bash command inside the router container
    # Params:
    #   String cmd: Command to execute
    # Return:
    #   None
    def run(self, cmd: str) -> None:
        full_cmd = f'docker exec {self.getNodeName()} /bin/bash -c "{cmd}"'
        try:
            subprocess.run(full_cmd, shell=True, check=True)
        except Exception as ex:
            logging.error(f"Error running command on {self.getNodeName()}: {str(ex)}")
            raise Exception(f"Error running command on {self.getNodeName()}: {str(ex)}")
        
    # Brief: Set IP to an interface using iproute2 (overrides Node's default to support CIDR injection)
    # Params:
    #   String ip: IP address to be set
    #   int mask: Integer that represents the network mask (e.g., 24, 30)
    #   String interfaceName: Interface to apply the IP
    # Return:
    #   None
    def setIp(self, ip: str, mask: int, interfaceName: str) -> None:
        cmd = f"docker exec {self.getNodeName()} ip addr add {ip}/{mask} dev {interfaceName}"
        try:
            subprocess.run(cmd, shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as ex:
            logging.error(f"Error setting IP on {self.getNodeName()} ({interfaceName}): {str(ex)}")
            raise Exception(f"Error setting IP on {self.getNodeName()} ({interfaceName}): {str(ex)}")
        
