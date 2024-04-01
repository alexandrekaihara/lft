from experiment.constants import *
from lft.ue import UE

class EmuPhyWireless:
    def __init__(self):
        self.ue = UE('ue1')

    def setup(self):
        self.ue.instantiate(dockerImage=SRSRAN_PERFSONAR_UHD_IMAGE, runCommand=USR_SBIN_INIT_COMMAND)
        self.ue.connectToInternet(EMU_PHY_WIRELESS_UE_IP_ADDR, 29, "uehost", "hostue")
        self.ue.setIp('10.0.0.2', 29, "uehost")
        self.ue.setDefaultGateway(EMU_PHY_WIRELESS_UE_IP_ADDR, "hostue")

        self.ue.setDeviceName("uhd")
        self.ue.setTxGain(25)
        self.ue.setRxGain(25)
        self.ue.setDeviceArgs(f"type=x300,addr={EMU_PHY_WIRELESS_USRP_IP_ADDR}")

        self.ue.start()

        self.ue.setHost(EMU_PHY_WIRELESS_UE_IP_ADDR)

    def tearDown(self):
        self.ue.delete()