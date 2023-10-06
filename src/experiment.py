import subprocess
from host import Host
from switch import Switch
from controller import Controller
from onos import ONOS
import paramiko

from os import getcwd
import signal
import sys

onos = ONOS("c1")
h1 = Host("h1")
h2 = Host("h2")
h3 = Host("h3")
h4 = Host("h4")
s1 = Switch("s1") #getcwd() +'/flows/'+"s1", '/home/pcap')
s2 = Switch("s2")

def createSwitch():
    print("[Experiment] Creating switch s1")
    print("... Instatiating container")
    s1.instantiate(networkMode='bridge')
    print("[Experiment] Creating switch s2")
    print("... Instatiating container")
    s2.instantiate()
    print("[Experiment] Switches created successfully")

def createONOS():

    print("[Experiment] Creating ONOS Controller")
    onos.instantiate()

def signal_handler(sig, frame):
    print("You've pressed Ctrl+C!")
    onos.delete()
    s1.delete()
    s2.delete()
    h1.delete()
    h2.delete()
    h3.delete()
    h4.delete()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

try:
    print("Starting experiment")
    createONOS()
    print("[Experiment] ONOS created sucessfully, wait for initialization and press y")
    inp = ''
    while(inp != 'y'):
        inp = input(" Proceed to switch creation? [y]")
    onos.activateONOSApps("172.17.0.2")
    createSwitch()
    print("[Experiment] Setting controller for the s1 and s2")
    s1.setController("172.17.0.2", 6653) # Onos container's IP (can be obtained with docker container inspect) and default port for OpenFlow
    s2.setController("172.17.0.2", 6653)

    print("[Experiment] Host creation, h1 and h2 connected to s1")
    print(" ... Instantiating h1")
    h1.instantiate() #dockerImage="perfsonar/testpoint")
    print(" ... Instantiating h2")
    h2.instantiate() #dockerImage="perfsonar/testpoint")
    print(" ... Connecting s1 to h1")
    s1.connect(h1, "s1h1", "h1s1")
    print(" ... Connecting s1 to h2")
    s1.connect(h2, "s1h2", "h2s1")
    print(" ... Setting IP addresses for h1 and h2")
    h1.setIp("192.168.0.3", 24, 'h1s1')
    h2.setIp("192.168.0.4", 24, 'h2s1')

    print("[Experiment] Host creation, h3 and h4 connected to s2")
    print(" ... Instantiating h3")
    h3.instantiate() #dockerImage="perfsonar/testpoint")
    print(" ... Instantiating h4")
    h4.instantiate() #dockerImage="perfsonar/testpoint")
    print(" ... Connecting s2 to h3")
    s2.connect(h3, "s2h3", "h3s2")
    print(" ... Connecting s2 to h4")
    s2.connect(h4, "s2h4", "h4s2")
    print(" ... Setting IP addresses for h3 and h4")
    h3.setIp("192.168.1.3", 24, 'h3s2')
    h4.setIp("192.168.1.4", 24, 'h4s2')
    print("[Experiment] Connecting switches")
    s1.connect(s2, "s1s2", "s2s1")

    print("[Experiment] Setting routes")
    h1.addRoute("192.168.1.0", 24, "h1s1")
    h2.addRoute("192.168.1.0", 24, "h2s1")
    h3.addRoute("192.168.0.0", 24, "h3s2")
    h4.addRoute("192.168.0.0", 24, "h4s2")

    s1.addRoute("192.168.1.0", 24, "s1s2")
    s2.addRoute("192.168.0.0", 24, "s2s1")

    print("[Experiment] Generating simple traffic for host detection")
    subprocess.run(f"docker exec h1 ping 192.168.0.4 -c 2", shell=True)
    subprocess.run(f"docker exec h3 ping 192.168.1.4 -c 2", shell=True)
    print("[Experiment] Setup complete!")

except Exception as e:
    onos.delete()
    s1.delete()
    s2.delete()
    h1.delete()
    h2.delete()
    h3.delete()
    h4.delete()
    raise(e)


print("[Experiment] Press ctrl+c to stop the program")
signal.pause()
