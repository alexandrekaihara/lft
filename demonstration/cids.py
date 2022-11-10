#!/usr/bin/env python
from gc import collect
import signal
import sys
import subprocess
from wsgiref.simple_server import ServerHandler, server_version
from host import Host
from switch import Switch
from controller import Controller
from configparser import ConfigParser
from node import Node
from os import getcwd
from globalvariables import *

class Seafile(Host):
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


def setLinuxClientFileConfig(node: LinuxClient, subnet: str, behaviour: str):
    printTerm(f"[LST2.0] Copying Configuration Files to Container {node.getNodeName()}")
    if subnet != external_subnet: aux = "internal"
    else: aux = "external"
    node.setAutomationScripts("automation")
    node.setPrinterIp(f"printersip/{subnet.split('.')[2]}")
    node.setSshIpList("sshiplist.ini")
    node.setClientBehaviour(f"client_behaviour/{behaviour}.ini")
    node.setServerConfig("serverconfig.ini")
    node.setIpListPort80(f"{aux}_ipListPort80.txt")        
    node.setIpList(f"{aux}_ipList.txt")
    node.setIpRange(f"{aux}_iprange.txt")


def setNetworkConfig(node: Node, bridge: Node, subnet: str, address: int, setFiles=True) -> Node:
    node.connect(bridge)
    printTerm(f"[LST2.0] ... Connecting to {bridge.getNodeName()}")
    node.setIp(subnet+str(address), 24, bridge)
    printTerm(f"[LST2.0] ... Setting IP {subnet+str(address)}")
    # Define default gateway of nodes
    if bridge == nodes['brint']: node.setDefaultGateway(int_gateway, bridge)
    if bridge == nodes['brex']:  node.setDefaultGateway(ex_gateway , bridge)
    printTerm(f"[LST2.0] ... Setting Default Gateway")
    # Add routes to enable nodes within internal subnet communicate with server subnet
    if subnet != server_subnet: node.addRoute(server_subnet+'0', 24, bridge)
    if subnet != management_subnet: node.addRoute(management_subnet+'0', 24, bridge)
    if subnet != office_subnet: node.addRoute(office_subnet+'0', 24, bridge)
    if subnet != developer_subnet: node.addRoute(developer_subnet+'0', 24, bridge)
    if subnet != external_subnet: node.addRoute(external_subnet+'0', 24, bridge)
    printTerm(f"[LST2.0] ... Adding new routes")
    if setFiles:
        subprocess.run(f"docker cp serverconfig.ini {node.getNodeName()}:/home/debian/serverconfig.ini", shell=True)
        subprocess.run(f"docker cp backup.py {node.getNodeName()}:/home/debian/backup.py", shell=True)


def createBridge(name: str, ip: str, gatewayIp: str, netflowPort=9000) -> None: 
    printTerm(f"[LST2.0] Creating Switch {name}")
    nodes[name] = Switch(name, getcwd()+'/flows/'+name, '/home/pcap')
    nodes[name].run('mkdir /home/pcap > /dev/null 2>&1')
    nodes[name].instantiate()
    printTerm("[LST2.0] ... Instantiating container")
    nodes[name].setIp(ip, 24)
    printTerm(f"[LST2.0] ... Setting IP {ip}")
    nodes[name].connectToInternet(gatewayIp, 24)
    printTerm(f"[LST2.0] ... Connecting to Internet through Host")


def createController(name: str, bridgeName: str, controllerIp: str, controllerPort: int) -> None:
    printTerm(f"[LST2.0] Creating Controller {name}")
    nodes[name] = Controller(name)
    nodes[name].instantiate()
    printTerm("[LST2.0] ... Instantiating container")
    nodes[name].connect(nodes[bridgeName])
    printTerm(f"[LST2.0] ... Connecting to Node {bridgeName}")
    nodes[name].setIp(controllerIp, 24, nodes[bridgeName])
    printTerm(f"[LST2.0] ... Setting IP {controllerIp}")
    nodes[name].initController(controllerIp, controllerPort)
    printTerm(f"[LST2.0] ... Initiating Ryu Controller at {controllerIp}:{controllerPort}")
    nodes[bridgeName].setController(controllerIp, controllerPort)
    printTerm(f"[LST2.0] ... Conecting Switch {bridgeName} to controller")
    

def createServer(name: str, serverImage: str, subnet: str,  address: int) -> None:
    printTerm(f"[LST2.0] Creating Server {name}")
    nodes[name] = Host(name)
    nodes[name].instantiate(serverImage)
    printTerm("[LST2.0] ... Instantiating container")
    setNetworkConfig(nodes[name], nodes['brint'], subnet, address)


def createLinuxClient(name, bridge: Node, subnet: str, address: int) -> None:
    printTerm(f"[LST2.0] Creating Client {name}")
    nodes[name] = LinuxClient(name)
    nodes[name].instantiate(linuxclient)
    printTerm("[LST2.0] ... Instantiating container")
    setNetworkConfig(nodes[name], bridge, subnet, address)


def createPrinter(name: str, subnet: str) -> None:
    printTerm(f"[LST2.0] Creating Printer {name}")
    nodes[name] = Host(name)
    nodes[name].instantiate(printerserver)
    printTerm("[LST2.0] ... Instantiating container")
    setNetworkConfig(nodes[name], nodes['brint'], subnet, 1)


def unmakeChanges():
    printTerm(f"[LST2.0] Unmaking Experiment. Deleting Containers")
    [node.delete() for _,node in nodes.items()]


def signal_handler(sig, frame):
    print('You pressed Ctrl+C!')
    unmakeChanges()
    sys.exit(0)


def collectLogs():
    printTerm(f"[LST2.0] Collecting Client Logs")
    hosts = ['e1', 'e2', 'm1', 'm2', 'm3', 'm4', 'o1', 'o2', 'd1', 'd2', 'd3', 'd4', 'd5', 'd6', 'd7', 'd8', 'd9', 'd10', 'd11', 'd12', 'd13']
    ips = ['50.3', '50.4', '200.2', '200.3', '200.4', '200.5', '210.2', '210.3', '220.2', '220.3', '220.4', '220.5', '220.6', '220.7', '220.8', '220.9', '220.10', '220.11', '220.12', '220.13', '220.14']
    def getLog(ip, host):
        subprocess.run(f'docker cp {host}:/home/debian/log/192.168.{ip}.log logs/192.168.{ip}.log > /dev/null 2>&1', shell=True)
    [getLog(ip, host) for ip, host in zip(ips, hosts)]


def printTerm(string: str) -> None:
    subprocess.run(f"echo \"{string}\"", shell=True)


# Capture the ctrl+c
signal.signal(signal.SIGINT, signal_handler)

try:
    printTerm("LST 2.0  Copyright (C) 2022\n\n\tThis program comes with ABSOLUTELY NO WARRANTY;\n\tThis is free software, and you are welcome to redistribute it\n\tunder certain conditions;\n\n")
    printTerm("[LST2.0] Iniciando o Experimento")    
    # Create folder to store the 
    subprocess.run("mkdir flows 2>/dev/null", shell=True)

    # Create Bridges and connect them
    createBridge('brint', brint_ip, int_gateway)
    createBridge('brex', brex_ip, ex_gateway)
    nodes['brex'].connect(nodes['brint'])

    subprocess.run(f"ip route add 192.168.200.0/24 dev veth-host-brint", shell=True)
    subprocess.run(f"ip route add 192.168.210.0/24 dev veth-host-brint", shell=True)
    subprocess.run(f"ip route add 192.168.220.0/24 dev veth-host-brint", shell=True)

    # Create seafile server
    nodes['seafile'] = Seafile('seafile')
    nodes['seafile'].instantiate()
    setNetworkConfig(nodes['seafile'], nodes['brint'], external_subnet, 1, setFiles=False)
    nodes['seafile'].updateServerConfig()

    # Create controllers
    createController('c1', 'brint', c1_ip, c1port)
    createController('c2', 'brex', c1_ip, c1port)

    # Create server subnet
    createServer('mail',   mailserver,   server_subnet, 1)
    createServer('file',   fileserver,   server_subnet, 2)
    createServer('web',    webserver,    server_subnet, 3)
    createServer('backup', backupserver, server_subnet, 4)

    # Set Management Subnet
    createPrinter('mprinter', management_subnet)
    createLinuxClient('m1', nodes['brint'], management_subnet, 2)
    createLinuxClient('m2', nodes['brint'], management_subnet, 3)
    createLinuxClient('m3', nodes['brint'], management_subnet, 4)
    createLinuxClient('m4', nodes['brint'], management_subnet, 5)
        
    # Set Office Subnet
    #createPrinter('oprinter', office_subnet)
    #createLinuxClient('o1', nodes['brint'], office_subnet, 2)
    #createLinuxClient('o2', nodes['brint'], office_subnet, 3)

    # Set Developer Subnet
    #createPrinter('dprinter', developer_subnet)
    #createLinuxClient('d1', nodes['brint'], developer_subnet, 2)
    #createLinuxClient('d2', nodes['brint'], developer_subnet, 3)
    #createLinuxClient('d3', nodes['brint'], developer_subnet, 4)
    #createLinuxClient('d4', nodes['brint'], developer_subnet, 5)
    #createLinuxClient('d5', nodes['brint'], developer_subnet, 6)
    #createLinuxClient('d6', nodes['brint'], developer_subnet, 7)
    #createLinuxClient('d7', nodes['brint'], developer_subnet, 8)
    #createLinuxClient('d8', nodes['brint'], developer_subnet, 9)
    #createLinuxClient('d9', nodes['brint'], developer_subnet, 10)
    #createLinuxClient('d10', nodes['brint'], developer_subnet, 11)
    #createLinuxClient('d11', nodes['brint'], developer_subnet, 12)
    #createLinuxClient('d12', nodes['brint'], developer_subnet, 13)
    #createLinuxClient('d13', nodes['brint'], developer_subnet, 14)

    # Set External Subnet
    #createServer('eweb', webserver, external_subnet, 2)
    #createLinuxClient('e1', nodes['brex'], external_subnet, 3)
    #createLinuxClient('e2', nodes['brex'], external_subnet, 4)

    # Set Configuration Files
    [setLinuxClientFileConfig(nodes[f'm{i}'], management_subnet, 'management') for i in range(1, 5)]
    #[setLinuxClientFileConfig(nodes[f'o{i}'], office_subnet, 'office') for i in range(1,3)]
    #[setLinuxClientFileConfig(nodes[f'd{i}'], developer_subnet, 'administrator') for i in range(1,3)]
    #[setLinuxClientFileConfig(nodes[f'd{i}'], developer_subnet, 'developer') for i in range(3,12)]
    #[setLinuxClientFileConfig(nodes[f'd{i}'], developer_subnet, 'attacker') for i in range(12,14)]
    #[setLinuxClientFileConfig(nodes[f'e{i}'], developer_subnet, 'external_attacker') for i in range(1,3)]

    nodes['brint'].collectFlows(path='home/pcap', sniffAll=True)
    nodes['brex'].collectFlows(path='home/pcap', sniffAll=True)
except Exception as ex:
    collectLogs()
    unmakeChanges()
    raise Exception(str(ex))

print('[LST2.0] Press CTRL+C to finish experiment')
signal.pause()
