from lft.ue import UE

class EmuPhyWireless:
    def __init__(self):
        self.ue = UE('ue1')
        self.usrpAddr = "192.168.107.2"

    def setup(self):
        self.ue.instantiate(dockerImage="alexandremitsurukaihara/lft:perfsonar-toolkit-srsRAN")
        self.ue.connectToInternet('10.0.0.1', 29, "uehost", "hostue")
        self.ue.setIp('10.0.0.2', 29, "uehost")
        self.ue.setDefaultGateway('10.0.0.1', "hostue")

        self.ue.setDeviceName("uhd")
        self.ue.setTxGain(25)
        self.ue.setRxGain(25)
        self.ue.setDeviceArgs(f"type=x300,addr={self.usrpAddr}")

        self.ue.start()

    def tearDown(self):
        self.ue.delete()