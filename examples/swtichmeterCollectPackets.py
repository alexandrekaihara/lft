from profissa_lft.host import Host
from profissa_lft.switchmeter import SwitchMeter
from time import sleep

h1 = Host('h1')
h2 = Host('h2')
s1 = SwitchMeter('s1')

h1.instantiate()
h2.instantiate()
s1.instantiate()

h1.connect(s1, "h1s1", "s1h1")
h2.connect(s1, "h2s1", "s1h2")

h1.setIp('10.0.0.1', 24, "h1s1")
h2.setIp('10.0.0.2', 24, "h2s1")

s1.connectToInternet('10.0.0.3', 24, "s1host", "hosts1")

h1.setDefaultGateway('10.0.0.3', "h1s1")
h2.setDefaultGateway('10.0.0.3', "h2s1")

# Collect some packets
filePath = "/home/packets"
s1.run(f"mkdir {filePath}")
s1.collectPacketsCICFlowMeter("s1", filePath, 10)
sleep(15)

h1.run("ping 10.0.0.2")
h2.run("ping 10.0.0.1")
sleep(30)

s1.copyContainerToLocal(filePath, "./")

h1.delete()
h2.delete()
s1.delete()