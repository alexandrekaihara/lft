from lft.host import Host

class EmuPhyWired:
    def __init__(self):
        self.h1 = Host("h1")
        
    def setup(self):    
        self.h1.instantiate(dockerImage="perfsonar/testpoint")
        self.h1.connectToInternet("10.0.0.1", 30, "h1host", "hosth1")
        self.h1.setIp("10.0.0.2", 24, "h1host")
        self.h1.setDefaultGateway("10.0.0.1", "h1host")

    def tearDown(self):
        self.h1.delete()