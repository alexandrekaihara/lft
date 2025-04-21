from profissa_lft.host import Host
from profissa_lft.switch import Switch
from profissa_lft.controller import Controller
from time import sleep

h1 = Host('h1')
h2 = Host('h2')
s1 = Switch('s1')
c1 = Controller('c1')

h1.instantiate()
h2.instantiate()
s1.instantiate()
c1.instantiate()

h1.connect(s1, "h1s1", "s1h1")
h2.connect(s1, "h2s1", "s1h2")
c1.connect(s1, "c1s1", "s1c1")

h1.setIp('10.0.0.1', 24, "h1s1")
h2.setIp('10.0.0.2', 24, "h2s1")
s1.setIp('10.0.0.3', 24, 's1')
c1.setIp('10.0.0.4', 24, 'c1s1')

c1.initController('10.0.0.4', 9001)
s1.setController('10.0.0.4', 9001)

s1.connectToInternet('10.0.0.5', 24, "s1host", "hosts1")

h1.setDefaultGateway('10.0.0.5', "h1s1")
h2.setDefaultGateway('10.0.0.5', "h2s1")
s1.setDefaultGateway('10.0.0.5', "s1")

# Collect some packets
filePath = "/home/packets"
fileName = "test.pcap"
s1.run(f"mkdir {filePath}")
s1.collectPackets(["s1"], f"{filePath}/{fileName}", 10)

h1.run("ping 10.0.0.2")
h2.run("ping 10.0.0.1")
sleep(12)

s1.copyContainerToLocal(filePath, "./")
