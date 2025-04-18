from profissa_lft.host import Host
from profissa_lft.switch import Switch
from profissa_lft.controller import Controller

h1 = Host('h1')
h2 = Host('h2')
s1 = Switch('s1')
s2 = Switch('s2')
c1 = Controller('c1')

h1.instantiate()
h2.instantiate()
s1.instantiate()
s2.instantiate()
c1.instantiate()

h1.connect(s1, "h1s1", "s1h1")
h2.connect(s2, "h2s2", "s2h2")
s1.connect(s2, "s1s2", "s2s1")
c1.connect(s1, "c1s1", "s1c1")
c1.connect(s2, "c1s2", "s2c1")

h1.setIp('10.0.0.1', 24, "h1s1")
h2.setIp('11.0.0.1', 24, "h2s2")
c1.setIp('12.0.0.1', 24, "c1s1")

# Need to set IP to the bridges to that it can connect to the controller and make part of the subnet to enabled internet communication
s1.setIp('12.0.0.2', 24, "s1")
s1.setIp('10.0.0.2', 24, "s1")
s2.setIp('12.0.0.3', 24, "s2")
s2.setIp('11.0.0.2', 24, "s2")

# Need to add route to enable communication with another subnet
h1.addRoute("11.0.0.0", 24, "h1s1")
h2.addRoute("10.0.0.0", 24, "h2s2")

c1.initController('12.0.0.1', 9001)
s1.setController('12.0.0.1', 9001)
s2.setController('12.0.0.1', 9001)

s1.connectToInternet('10.0.0.3', 24, "s1host", "hosts1")
s2.connectToInternet('11.0.0.3', 24, "s2host", "hosts2")

h1.setDefaultGateway('10.0.0.3', "h1s1")
h2.setDefaultGateway('11.0.0.3', "h2s2")
c1.setDefaultGateway('10.0.0.3', "c1s1")
