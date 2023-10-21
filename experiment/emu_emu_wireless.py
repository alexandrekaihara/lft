from lft.switch import Switch
from lft.ue import UE
from lft.epc import EPC
from lft.enb import EnB
import time

class EmuEmuWireless:
    def __init__(self):
        self.epc = EPC('epc')
        self.enb = EnB("enb")
        self.ue = UE('ue1')

    def setup(self):
        self.epc.instantiate(dockerImage="alexandremitsurukaihara/lft:perfsonar-toolkit-srsRAN")
        self.enb.instantiate(dockerImage="alexandremitsurukaihara/lft:perfsonar-toolkit-srsRAN")
        self.ue.instantiate(dockerImage="alexandremitsurukaihara/lft:perfsonar-toolkit-srsRAN")

        self.enb.connect(self.epc, "enbepc", "epcenb")
        self.ue.connect(self.enb, "ue1enb", "enbue1")

        self.self.epc.setIp('10.0.0.1', 24, "epcenb")
        self.enb.setIp('10.0.0.2', 24, "enbepc")
        self.enb.setIp('11.0.0.1', 30, "enbue1")
        self.enb.setIp('11.0.0.5', 30, "enbue2")
        self.ue.setIp('11.0.0.2', 29, "ue1enb")

        self.enb.connectToInternet('10.0.0.6', 24, "epchost", "hostepc")

        self.epc.setDefaultGateway('10.0.0.6', "epchost")
        self.enb.setDefaultGateway('10.0.0.6', "enbepc")
        self.ue.setDefaultGateway('10.0.0.2', "ue1enb")

        # Define EPC config
        self.epc.setEPCAddress("10.0.0.1")
        self.epc.addNewUE(self.ue.getNodeName(), "001010123456780", "172.16.0.2")

        # Define ENB Config
        self.enb.setEPCAddress("10.0.0.1")
        self.enb.setEnBAddress("10.0.0.2")
        self.enb.setMultiUEEnBAddr("11.0.0.1", 2101, '11.0.0.1', 2100)
        self.enb.setMultiUEUE1Addr("11.0.0.2", 2001, "11.0.0.1", 2000)
        self.enb.setMultiUEUE2Addr("11.0.0.6", 2011, "11.0.0.5", 2010)

        # Define UE Config
        self.ue.setUEID("001010123456780")

        self.epc.start()
        self.enb.starGnuRadioMultiUE()
        self.enb.start("11.0.0.1", 2101, "11.0.0.1", 2100)
        time.sleep(5)  
        self.ue.start("11.0.0.2", 2001, "11.0.0.1", 2000)

    def tearDown(self):
        self.epc.delete()
        self.enb.delete()
        self.ue.delete()