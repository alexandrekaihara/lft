from profissa_lft.perfsonar import Perfsonar
from time import sleep
from experiment.constants import *

class EmuEmuWired:
    def __init__(self):
        self.h1 = Perfsonar('h1')
        self.h2 = Perfsonar('h2')

    def setup(self):
        self.h1.instantiate(PERFSONAR_TESTPOINT_UBUNTU, runCommand=USR_SBIN_INIT_COMMAND)
        self.h2.instantiate(PERFSONAR_TESTPOINT_UBUNTU, runCommand=USR_SBIN_INIT_COMMAND)
        
        self.h1.connect(self.h2, "h1h2", "h2h1")
        self.h1.setIp(EMU_EMU_WIRED_H1_IP, 24, "h1h2")
        self.h2.setIp(EMU_EMU_WIRED_H2_IP, 24, "h2h1")
        
        self.h1.connectToInternet(EMU_EMU_WIRED_HOST_IP, 24, "h1host", "hosth1")
        self.h1.setIp("192.0.0.2", 24, "h1host")

        self.h1.enableForwarding("h1host", "h1h2")
        self.h1.setDefaultGateway(EMU_EMU_WIRED_HOST_IP, "h1host")
        self.h2.setDefaultGateway(EMU_EMU_WIRED_H1_IP, "h2h1")

        self.h1.addRouteOnHost('10.0.0.0', 24, 'hosth1', '192.0.0.2')

        self.h1.setHost(EMU_EMU_WIRED_H1_IP)
        self.h2.setHost(EMU_EMU_WIRED_H2_IP)

        self.h1.readLimitFile()
        self.h2.readLimitFile()

        self.h1.addRouteException("192.0.0.0", 24)
        self.h2.addRouteException("192.0.0.0", 24)

        self.h1.saveLimitFile()
        self.h2.saveLimitFile()

        self.__startPerfsonarServices()

        self.h1.setInterfaceProperties("h1h2", "935mbit", "0.3ms", "0.15ms")
        self.h2.setInterfaceProperties("h2h1", "935mbit", "0.3ms", "0.15ms")
        
    def __startPerfsonarServices(self):
         self.h1.run("service pscheduler-runner start && service pscheduler-ticker start && service pscheduler-scheduler start && service pscheduler-archiver start")
         sleep(5)
         self.h2.run("service pscheduler-runner start && service pscheduler-ticker start && service pscheduler-scheduler start && service pscheduler-archiver start")


    def tearDown(self):
        self.h1.delete()
        self.h2.delete()
