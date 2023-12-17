from lft.perfsonar import Perfsonar


class EmuEmuWired:
    def __init__(self):
        self.h1 = Perfsonar('h1')
        self.h2 = Perfsonar('h2')

    def setup(self):
        self.h1.instantiate("alexandremitsurukaihara/lft:perfsonar-testpoint-ubuntu", runCommand='/usr/sbin/init')
        self.h2.instantiate("alexandremitsurukaihara/lft:perfsonar-testpoint-ubuntu", runCommand='/usr/sbin/init')
        
        self.h1.connect(self.h2, "h1h2", "h2h1")
        self.h1.setIp('10.0.0.1', 24, "h1h2")
        self.h2.setIp('10.0.0.2', 24, "h2h1")
        
        self.h1.connectToInternet('192.0.0.1', 24, "h1host", "hosth1")
        self.h1.setIp("192.0.0.2", 24, "h1host")

        self.h1.enableForwarding("h1host", "h1h2")
        self.h1.setDefaultGateway('192.0.0.1', "h1host")
        self.h2.setDefaultGateway('10.0.0.1', "h2h1")

        self.h1.addRouteOnHost('10.0.0.0', 24, 'hosth1', '192.0.0.2')

        self.h1.setHost('10.0.0.1')
        self.h2.setHost('10.0.0.2')

        self.h1.readLimitFile()
        self.h2.readLimitFile()

        self.h1.addRouteException("192.0.0.0", 24)
        self.h2.addRouteException("192.0.0.0", 24)

        self.h1.saveLimitFile()
        self.h2.saveLimitFile()

    def tearDown(self):
        self.h1.delete()
        self.h2.delete()
