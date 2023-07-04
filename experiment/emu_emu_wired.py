from host import Host
from switch import Switch

s1 = Switch("s1")
h1 = Host("h1")
h2 = Host("h2")

s1.instantiate()
h1.instantiate(dockerImage="perfsonar/testpoint")
h2.instantiate(dockerImage="perfsonar/testpoint")

s1.connect(h1, "s1h1", "h1s1")
s1.connect(h2, "s1h2", "h2s1")
s1.connectToInternet("10.0.0.1", 29, "s1host", "hosts1")

h1.setIp("10.0.0.2", 32, 'h1s1')
h2.setIp("10.0.0.3", 32, 'h2s1')

h1.setDefaultGateway("10.0.0.1", "h1s1")
h2.setDefaultGateway("10.0.0.1", "h2s1")