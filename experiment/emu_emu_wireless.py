from lft.ue import UE
from lft.epc import EPC
from lft.enb import EnB
import time
import subprocess

class EmuEmuWireless:
    def __init__(self):
        self.epc = EPC('epc')
        self.enb = EnB("enb")
        self.ue = UE('ue')

    def setup(self):
        self.epc.instantiate(dockerImage="alexandremitsurukaihara/lft:srsran-perfsonar-uhd3", runCommand='/usr/sbin/init')
        self.enb.instantiate(dockerImage="alexandremitsurukaihara/lft:srsran-perfsonar-uhd3")
        self.ue.instantiate(dockerImage="alexandremitsurukaihara/lft:srsran-perfsonar-uhd3", runCommand='/usr/sbin/init')

        self.enb.connect(self.epc, "enbepc", "epcenb")
        self.ue.connect(self.enb, "ueenb", "enbue")

        self.epc.connectToInternet('9.0.0.2', 24, "epchost", "hostepc")
        self.ue.connectToInternet('12.0.0.2', 24, "uehost", "hostue")

        self.epc.setIp('9.0.0.1', 24, "epchost")
        self.epc.setIp('10.0.0.1', 24, "epcenb")
        self.enb.setIp('10.0.0.2', 24, "enbepc")
        self.enb.setIp('11.0.0.1', 30, "enbue")
        self.ue.setIp('12.0.0.1', 24, "uehost")
        self.ue.setIp('11.0.0.2', 29, "ueenb")

        self.epc.setDefaultGateway('10.0.0.3', "epchost")
        self.enb.setDefaultGateway('10.0.0.3', "enbepc")
        self.ue.setDefaultGateway('10.0.0.2', "ueenb")

        self.enb.acceptPacketsFromInterface("enbue")

        # Define EPC config
        self.epc.setEPCAddress("10.0.0.1")
        self.epc.addNewUE(self.ue.getNodeName(), "001010123456780", "172.16.0.2")

        # Define ENB Config
        self.enb.setEPCAddress("10.0.0.1")
        self.enb.setEnBAddress("10.0.0.2")
        self.enb.setSingleUEEnBAddr("11.0.0.1", 2101, '11.0.0.1', 2100)
        self.enb.setSingleUEUEAddr("11.0.0.2", 2001, "11.0.0.1", 2000)

        # Define UE Config
        self.ue.setUEID("001010123456780")

        self.epc.start()
        self.enb.starGnuRadioSingleUE()
        self.enb.start("11.0.0.1", 2101, "11.0.0.1", 2100)
        time.sleep(5)  
        self.ue.start("--rf.device_name=zmq --rf.device_args=\"tx_port=tcp://11.0.0.2:2001,rx_port=tcp://11.0.0.1:2000,id=ue,base_srate=23.04e6\"")

        self.ue.setHost('172.16.0.2')
        self.epc.setHost('172.16.0.1')

        self.epc.enableForwarding("epchost", "srs_spgw_sgi")
        self.ue.enableForwarding("uehost", "tun_srsue")

        subprocess.run("ip route add 172.16.0.2/32 via 12.0.0.1 dev hostue", shell=True)
        subprocess.run("ip route add 172.16.0.1/32 via 9.0.0.1 dev hostepc", shell=True)
#        self.ue.readLimitFile()
#        self.enb.readLimitFile()

#        self.u.addRouteException("192.0.0.0", 24)
#        self.h2.addRouteException("192.0.0.0", 24)

#        self.h1.saveLimitFile()
#        self.h2.saveLimitFile()

    def tearDown(self):
        self.epc.delete()
        self.enb.delete()
        self.ue.delete()
