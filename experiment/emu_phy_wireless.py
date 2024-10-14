from experiment.constants import *
from profissa_lft.ue import UE
from subprocess import run

class EmuPhyWireless:
    def __init__(self):
        self.ue = UE('ue1')

    def setup(self):
        self.ue.instantiate(dockerImage=SRSRAN_PERFSONAR_UHD_IMAGE, runCommand=USR_SBIN_INIT_COMMAND)
        self.ue.connectToInternet(EMU_PHY_WIRELESS_UE_IP_ADDR, 29, "uehost", "hostue")
        self.ue.setIp('10.0.0.2', 29, "uehost")
        self.ue.setDefaultGateway(EMU_PHY_WIRELESS_UE_IP_ADDR, "uehost")
        self.ue.setMtuSize("uehost", 9000)
        run("ifconfig hostue mtu 9000", shell=True)

        self.ue.setDeviceName("uhd")
        self.ue.setTxGain(str(25))
        self.ue.setRxGain(str(25))
        self.ue.setDeviceArgs(f"type=x300,addr={EMU_PHY_WIRELESS_USRP_IP_ADDR}")

        self.ue.setHost(EMU_PHY_WIRELESS_UE_IP_ADDR)
        self.ue.start()
        

    def tearDown(self):
        self.ue.delete()