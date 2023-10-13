# Standard libraries imports
from configparser import ConfigParser
import subprocess
from os import getcwd
import signal
import sys

# Local imports
from host import Host
from node import Node
from switch import Switch
from onos import ONOS
from atomix import Atomix
from global_variables import *


class Seafile(Host):
    def instantiate(self):
        super().instantiate(dockerImage=seafileserver)
    def updateServerConfig(self) -> None:
        self.copyContainerToLocal("/home/seafolder", "seafolder")
        out = subprocess.run("cat seafolder", shell=True, capture_output=True).stdout.decode('utf8')
        parser = ConfigParser()
        parser.read('serverconfig.ini')
        parser.set("50", "seafolder",  out)
        parser.set("200", "seafolder", out)
        parser.set("210", "seafolder", out)
        parser.set("220", "seafolder", out)
        with open('serverconfig.ini', 'w') as configfile:
            parser.write(configfile)

class LinuxClient(Host):
    def setAutomationScripts(self, path) -> None:
        self.copyLocalToContainer(path, "/home/debian/automation")
    def setPrinterIp(self, path) -> None:
        self.copyLocalToContainer(path, "/home/debian/automation/packages/system/printerip")
    def setSshIpList(self, path) -> None:
        self.copyLocalToContainer(path, "/home/debian/automation/packages/system/sshiplist.ini")
    def setClientBehaviour(self, path) -> None:
        self.copyLocalToContainer(path, "/home/debian/automation/packages/system/config.ini")
    def setServerConfig(self, path) -> None:
        self.copyLocalToContainer(path, "/home/debian/automation/packages/system/serverconfig.ini")
    def setIpListPort80(self, path) -> None:
        self.copyLocalToContainer(path, "/home/debian/automation/packages/attacking/ipListPort80.txt")
    def setIpList(self, path) -> None:
        self.copyLocalToContainer(path, "/home/debian/automation/packages/attacking/ipList.txt")
    def setIpRange(self, path) -> None:
        self.copyLocalToContainer(path, "/home/debian/automation/packages/attacking/iprange.txt")

def createBridge(name: str): #, ip: str, gatewayIp: str):
    print(f" ... Creating switch {name}")
    nodes[name] = Switch(name, getcwd()+'/flows/'+name, '/home/pcap')
    print(f" ... Creating switch {name}: Instantiating")
    nodes[name].instantiate(networkMode='bridge')
    print(f" ... Creating switch {name}: MKDIR")
    nodes[name].run('mkdir /home/pcap > /dev/null 2>&1')
    print(f" ... {name} created successfully")

def createController(name: str):
    print(f" ... Creating controller {name}")
    nodes[name] = ONOS(name)
    mapports = False
    if name == "c1": mapports = True
    nodes[name].instantiate(mapPorts=mapports)
    print(" ... Creating config folder")
    subprocess.call(f"docker exec {name} mkdir /root/onos/config", shell=True)
    print(f" ... Controller {name} created successfully")

def setNetworkConfig(node: Node, bridge: Node, subnet: str, address: int, setFiles=True):
    print(f" ... Set networking configuration for {node.getNodeName()}")
    print(f" ... Connecting node to {bridge.getNodeName()}")
    node.connect(bridge, f"{node.getNodeName()}{bridge.getNodeName()}", f"{bridge.getNodeName()}{node.getNodeName()}")
    print(" ... Setting node IP - Interface connected to a bridge")
    node.setIp(subnet+str(address), 24, f"{node.getNodeName()}{bridge.getNodeName()}")
    # print(" ... Setting default gateway")
    print(" ... Adding routes to other subnets")
    if subnet != server_subnet: node.addRoute(server_subnet+'0', 24, node.getNodeName() + bridge.getNodeName())
    if subnet != management_subnet: node.addRoute(management_subnet+'0', 24, node.getNodeName() + bridge.getNodeName())
    if subnet != office_subnet: node.addRoute(office_subnet+'0', 24, node.getNodeName() + bridge.getNodeName())
    if subnet != developer_subnet: node.addRoute(developer_subnet+'0', 24, node.getNodeName() + bridge.getNodeName())
    if subnet != external_subnet: node.addRoute(external_subnet+'0', 24, node.getNodeName() + bridge.getNodeName())
    if setFiles:
        subprocess.run(f"docker cp serverconfig.ini {node.getNodeName()}:/home/debian/serverconfig.ini", shell=True)
        # subprocess.run(f"docker cp backup.py {node.getNodeName()}:/home/debian/backup.py", shell=True)

def setLinuxClientFileConfig(node: LinuxClient, subnet: str, behaviour: str):
    print(f"[LFT] Copying Configuration Files to Container {node.getNodeName()}")
    if subnet != external_subnet: aux = "internal"
    else: aux = "external"
    node.setAutomationScripts("automation")
    node.setPrinterIp(f"printersip/{subnet.split('.')[2]}")
    node.setSshIpList("sshiplist.ini")
    node.setClientBehaviour(f"client_behaviour/{behaviour}.ini")
    node.setServerConfig("serverconfig.ini")
    node.setIpListPort80(f"attack/{aux}_ipListPort80.txt")        
    node.setIpList(f"attack/{aux}_ipList.txt")
    node.setIpRange(f"attack/{aux}_iprange.txt")

def createLinuxClient(name:str, bridge: Node, subnet: str, address: int) -> None:
    print(f"[LFT] Creating client {name}")
    nodes[name] = LinuxClient(name)
    print(" ... Instantiating container")
    nodes[name].instantiate(linuxclient)
    setNetworkConfig(nodes[name], bridge, subnet, address)

def createPrinter(name: str, subnet: str) -> None:
    print(f"[LFT] Creating printer {name}")
    nodes[name] = Host(name)
    print(" ... Instantiating container")
    nodes[name].instantiate(printerserver)
    setNetworkConfig(nodes[name], nodes["brint"], subnet, 1)

def createServer(name: str, serverImage: str, subnet: str, address: int):
    print(f"[LFT] ... Creating server {name}")
    nodes[name] = Host(name)
    print(" ... Instantiating container")
    nodes[name].instantiate(serverImage)
    setNetworkConfig(nodes[name], nodes["brint"], subnet, address)

def signal_handler(sig, frame):
    print("You've pressed Ctrl+C!")
    print(f"[LFT] Unmaking Experiment. Deleting Containers")
    [node.delete() for _,node in nodes.items()]
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

try:
    print("[LFT] Initializing demonstration")

    print(" ... Creating flows folder on host machine")
    subprocess.run("mkdir flows 2>/dev/null", shell=True)

    print("[LFT] ... Creating Atomix node")
    nodes["a1"] = Atomix("a1")
    nodes["a1"].instantiate("./conf")
    print(" ... Restarting Atomix to apply configurations")
    subprocess.run("docker restart a1", shell=True)
    print(" ... Atomix created successfully")

    print("[LFT] ... Creating ONOS controllers")
    createController("c1")
    createController("c2")

    print(" ... Copying configuration files to /root/onos/config")
    # Using call because of its blocking behavior
    subprocess.call(f"docker cp onos_config/cluster-1.json c1:/root/onos/config/cluster.json", shell=True)
    subprocess.call(f"docker cp onos_config/cluster-2.json c2:/root/onos/config/cluster.json", shell=True)


    print(" ... Restarting ONOS containers to apply configurations")
    subprocess.run("docker restart c1", shell=True)
    subprocess.run("docker restart c2", shell=True)

    print(" ... ONOS created sucessfully, wait for initialization and press y")
    inp = ''
    while(inp != 'y'):
        inp = input(" Proceed to switch creation? [y]")
    nodes["c1"].activateONOSApps("172.17.0.3")
    nodes["c2"].activateONOSApps("172.17.0.4")

    print("[LFT] ... Creating internal and external bridges")
    createBridge("brint")
    createBridge("brext")

    print(" ... Setting controllers for the bridges")
    nodes["brint"].setController("172.17.0.3", 6653)
    nodes["brext"].setController("172.17.0.4", 6653)

    print(" ... Connecting the bridges")
    nodes["brint"].connect(nodes["brext"], "brintbrext", "brextbrint")

    # Creating Seafile Server
    print("[LFT] ... Creating Seafile server")
    nodes['seafile'] = Seafile('seafile')
    nodes['seafile'].instantiate()
    setNetworkConfig(nodes['seafile'], nodes['brint'], external_subnet, 1, setFiles=False)
    nodes['seafile'].updateServerConfig()
    
    # Create server subnet
    print("[LFT] ... Creating server subnet")
    createServer('mail',   mailserver,   server_subnet, 1)
    createServer('file',   fileserver,   server_subnet, 2)
    createServer('web',    webserver,    server_subnet, 3)
    createServer('backup', backupserver, server_subnet, 4)

    # Create Management Subnet
    print("[LFT] ... Creating management subnet")
    createPrinter('mprinter', management_subnet)
    createLinuxClient('m1', nodes['brint'], management_subnet, 2)
    createLinuxClient('m2', nodes['brint'], management_subnet, 3)
    createLinuxClient('m3', nodes['brint'], management_subnet, 4)
    #createLinuxClient('m4', nodes['brint'], management_subnet, 5)
    
    # Set Office Subnet
    print("[LFT] ... Creating office subnet")
    createPrinter("oprinter", office_subnet)
    createLinuxClient("o1", nodes["brint"], office_subnet, 2)
    createLinuxClient("o2", nodes["brint"], office_subnet, 3)

    # Set Developer Subnet
    print("[LFT] ... Creating developer subnet")
    createPrinter('dprinter', developer_subnet)
    createLinuxClient('d1', nodes['brint'], developer_subnet, 2)
    createLinuxClient('d2', nodes['brint'], developer_subnet, 3)
    createLinuxClient('d3', nodes['brint'], developer_subnet, 4)
    createLinuxClient('d4', nodes['brint'], developer_subnet, 5)
    createLinuxClient('d5', nodes['brint'], developer_subnet, 6)
    createLinuxClient('d6', nodes['brint'], developer_subnet, 7)
    createLinuxClient('d7', nodes['brint'], developer_subnet, 8)
    createLinuxClient('d8', nodes['brint'], developer_subnet, 9)
    createLinuxClient('d9', nodes['brint'], developer_subnet, 10)
    createLinuxClient('d10', nodes['brint'], developer_subnet, 11)
    createLinuxClient('d11', nodes['brint'], developer_subnet, 12)
    createLinuxClient('d12', nodes['brint'], developer_subnet, 13)
    createLinuxClient('d13', nodes['brint'], developer_subnet, 14)

    # Set External Subnet
    print("[LFT] ... Creating external subnet")
    createServer('eweb', webserver, external_subnet, 2)
    createLinuxClient('e1', nodes['brext'], external_subnet, 3)
    createLinuxClient('e2', nodes['brext'], external_subnet, 4)

    # Set Configuration Files
    [setLinuxClientFileConfig(nodes[f'm{i}'], management_subnet, 'management') for i in range(1, 5)]
    [setLinuxClientFileConfig(nodes[f'o{i}'], office_subnet, 'office') for i in range(1,3)]
    [setLinuxClientFileConfig(nodes[f'd{i}'], developer_subnet, 'administrator') for i in range(1,3)]
    [setLinuxClientFileConfig(nodes[f'd{i}'], developer_subnet, 'developer') for i in range(3,12)]
    [setLinuxClientFileConfig(nodes[f'd{i}'], developer_subnet, 'attacker') for i in range(12,14)]
    [setLinuxClientFileConfig(nodes[f'e{i}'], developer_subnet, 'external_attacker') for i in range(1,3)]

except Exception as e:
    [node.delete() for _,node in nodes.items()]
    raise(e)

print("[LFT] Press ctrl+c to stop the program")
signal.pause()