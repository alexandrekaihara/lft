import subprocess

from profissa_lft.host import Host
from switch_modified import Switch
from profissa_lft.controller import Controller
from onos import ONOS
import paramiko

from os import getcwd
import signal
import sys

c1 = Controller("c1")

h1 = Host("h1")
h2 = Host("h2")
h3 = Host("h3")
middlebox = Host("middlebox")

s1 = Switch("s1") #getcwd() +'/flows/'+"s1", '/home/pcap')
s2 = Switch("s2")

nodes = {}

def createSwitch():
    print("[Experiment] Creating switch s1")
    print("... Instatiating container")
    s1.instantiate(networkMode='bridge')
    print("[Experiment] Creating switch s2")
    print("... Instatiating container")
    s2.instantiate(networkMode='bridge')
    print("[Experiment] Switches created successfully")

def createController(name: str):
    print(f" ... Creating controller {name}")
    nodes[name] = ONOS(name)
    mapports = False
    if name == "c1": mapports = True
    nodes[name].instantiate(mapPorts=mapports)
    print(" ... Creating config folder")
    subprocess.call(f"docker exec {name} mkdir /root/onos/config", shell=True)
    print(f" ... Controller {name} created successfully")

def signal_handler(sig, frame):
    print("You've pressed Ctrl+C!")
    [node.delete() for _,node in nodes.items()]
    s1.delete()
    s2.delete()
    h1.delete()
    h2.delete()
    h3.delete()
    middlebox.delete()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

try:
    print("Starting experiment")
    print("[LFT] ... Creating ONOS controller")
    createController("c1")

    print("[Experiment] ONOS created sucessfully, wait for initialization and press y")
    inp = ''
    while(inp != 'y'):
        inp = input(" Proceed to switch creation? [y]")

    nodes["c1"].activateONOSApps("172.17.0.2")
    createSwitch()
    print("[Experiment] Setting controller for the s1 and s2")
    s1.setController("172.17.0.2", 6653) # Onos container's IP (can be obtained with docker container inspect) and default port for OpenFlow
    s2.setController("172.17.0.2", 6653)

    print(["[Experiment] Creating Hosts"])
    print(" ... Instantiating h1")
    h1.instantiate() #dockerImage="perfsonar/testpoint")
    print(" ... Instantiating h2")
    h2.instantiate()
    print(" ... Instantiating h3")
    h3.instantiate() #dockerImage="perfsonar/testpoint")
    print(" ... Instantiating middlebox")
    middlebox.instantiate()

    print("[Experiment] Connecting Nodes")
    s1.connect(h1, "s1h1", "h1s1")
    s1.connect(h2, "s1h2", "h2s1")

    s2.connect(h3, "s2h3", "h3s2")
    s2.connect(middlebox, "s2middlebox", "middleboxs2")

    s1.connect(s2, "s1s2", "s2s1")
    
    h1.setIp("192.168.0.1", 24, "h1s1")
    h2.setIp("192.168.0.2", 24, "h2s1")
    h3.setIp("192.168.1.3", 24, "h3s2")
    middlebox.setIp("192.168.1.4", 24, "middleboxs2")

    s1.addRoute("192.168.1.0", 24, "s1s2")
    s2.addRoute("192.168.0.0", 24, "s2s1")

    print("[Experiment] Generating simple traffic for host detection")
    subprocess.run(f"docker exec h1 ping 192.168.0.2 -c 2", shell=True)
    subprocess.run(f"docker exec h3 ping 192.168.1.4 -c 2", shell=True)

except Exception as e:
    [node.delete() for _,node in nodes.items()]
    s1.delete()
    s2.delete()
    h1.delete()
    h2.delete()
    h3.delete()
    middlebox.delete()
    raise(e)

print("[Experiment] Press ctrl+c to stop the program")
signal.pause()
