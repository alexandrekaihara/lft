from lft.host import Host
from lft.switch import Switch


class EmuWired:
    def __init__(self):
        self.h1 = Host('h1')
        self.h2 = Host('h2')
        self.s1 = Switch('s1')

    def setup(self):
        self.h1.instantiate("perfsonar/testpoint")
        self.h2.instantiate("perfsonar/testpoint")
        self.s1.instantiate()

        self.h1.connect(self.s1, "h1s1", "s1h1")
        self.h2.connect(self.s1, "h2s1", "s1h2")

        self.h1.setIp('10.0.0.1', 24, "h1s1")
        self.h2.setIp('10.0.0.2', 24, "h2s1")

        self.s1.connectToInternet('10.0.0.4', 24, "s1host", "hosts1")

        self.h1.setDefaultGateway('10.0.0.4', "h1s1")
        self.h2.setDefaultGateway('10.0.0.4', "h2s1")

    def tearDown(self):
        self.h1.delete()
        self.h2.delete()
        self.s1.delete()