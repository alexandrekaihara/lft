from lft.host import Host
from experiment.constants import *


class EmuPhyWired:
    def __init__(self):
        self.h1 = Host("h1")
    def setup(self):    
        self.h1.instantiate(dockerImage=PERFSONAR_TESTPOINT_UBUNTU, runCommand=USR_SBIN_INIT_COMMAND)
        self.h1.connectToInternet("10.0.0.1", 30, "h1host", "hosth1")
        self.h1.setIp(EMU_PHY_WIRED_H1_IP, 24, "h1host")
        self.h1.setDefaultGateway("10.0.0.1", "h1host")
        self.h1.setHost('10.0.0.1')
        self.h1.setInterfaceTraffic("h1host", "1gbit", 0.571, 1600)
    def tearDown(self):
        self.h1.delete()