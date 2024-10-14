from profissa_lft.switch import Switch
from profissa_lft.ue import UE
from profissa_lft.epc import EPC
from profissa_lft.enb import EnB
import time

epc = EPC('epc')
enb = EnB("enb")
ue2 = UE('ue2')
ue1 = UE('ue1')

epc.instantiate(dockerImage="alexandremitsurukaihara/lft:perfsonar-toolkit-srsRAN")
enb.instantiate(dockerImage="alexandremitsurukaihara/lft:perfsonar-toolkit-srsRAN")
ue2.instantiate(dockerImage="alexandremitsurukaihara/lft:perfsonar-toolkit-srsRAN")
ue1.instantiate(dockerImage="alexandremitsurukaihara/lft:perfsonar-toolkit-srsRAN")

enb.connect(epc, "enbepc", "epcenb")
ue1.connect(enb, "ue1enb", "enbue1")
ue2.connect(enb, "ue2enb", "enbue2")

epc.setIp('10.0.0.1', 24, "epcenb")
enb.setIp('10.0.0.2', 24, "enbepc")
enb.setIp('11.0.0.1', 30, "enbue1")
enb.setIp('11.0.0.5', 30, "enbue2")
ue1.setIp('11.0.0.2', 29, "ue1enb")
ue2.setIp('11.0.0.6', 29, "ue2enb")

enb.connectToInternet('10.0.0.6', 24, "epchost", "hostepc")

epc.setDefaultGateway('10.0.0.6', "epchost")
enb.setDefaultGateway('10.0.0.6', "enbepc")
ue1.setDefaultGateway('10.0.0.2', "ue1enb")
ue2.setDefaultGateway('10.0.0.2', "ue2enb")

# Define EPC config
epc.setEPCAddress("10.0.0.1")
epc.addNewUE(ue1.getNodeName(), "001010123456780", "172.16.0.2")
epc.addNewUE(ue2.getNodeName(), "001010123456789", "172.16.0.3")

# Define ENB Config
enb.setEPCAddress("10.0.0.1")
enb.setEnBAddress("10.0.0.2")
enb.setMultiUEEnBAddr("11.0.0.1", 2101, '11.0.0.1', 2100)
enb.setMultiUEUE1Addr("11.0.0.2", 2001, "11.0.0.1", 2000)
enb.setMultiUEUE2Addr("11.0.0.6", 2011, "11.0.0.5", 2010)

# Define UE Config
ue1.setUEID("001010123456780")
ue2.setUEID("001010123456789")

epc.start()
enb.starGnuRadioMultiUE()
enb.start("11.0.0.1", 2101, "11.0.0.1", 2100)
time.sleep(5)  
ue1.start("11.0.0.2", 2001, "11.0.0.1", 2000)
ue2.start("11.0.0.6", 2011, "11.0.0.5", 2010)
