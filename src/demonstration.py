# Standard libraries imports
import subprocess
from os import getcwd
import signal
import sys

# Local imports
from switch import Switch
from onos import ONOS
from global_variables import *


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
    print(" ... Copying cluster.json file to /config folder")
    nodes[name].copyLocalToContainer("./conf/cluster.json", "/config/cluster.json")
    print(f" ... Controller {name} created successfully")

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

    print(" ... Creating ONOS controllers")
    createController("c1")
    createController("c2")

    print(" ... ONOS created sucessfully, wait for initialization and press y")
    inp = ''
    while(inp != 'y'):
        inp = input(" Proceed to switch creation? [y]")
    nodes["c1"].activateONOSApps("172.17.0.2")
    nodes["c2"].activateONOSApps("172.17.0.3")

    print(" ... Creating internal and external bridges")
    createBridge("brint")
    createBridge("brext")

    print(" ... Setting controllers for the bridges")
    nodes["brint"].setController("172.17.0.2", 6653)
    nodes["brext"].setController("172.17.0.3", 6653)

    print(" ... Connecting the bridges")
    nodes["brint"].connect(nodes["brext"], "brintbrext", "brextbrint")

except Exception as e:
    [node.delete() for _,node in nodes.items()]
    raise(e)

print("[LFT] Press ctrl+c to stop the program")
signal.pause()