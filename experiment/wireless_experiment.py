from experiment.experiment import *
from experiment.emu_emu_wireless import EmuEmuWireless
from experiment.emu_phy_wireless import EmuPhyWireless


emuEmu = EmuEmuWireless()
emuEmu.setup()
runExperiments("wireless_emu_emu_", "172.16.0.1", "172.16.0.2")
emuEmu.tearDown()

emuPhy = EmuPhyWireless()
emuPhy.setup()
runExperiments("wireless_emu_phy_", "172.16.0.1", "172.16.0.2")
emuPhy.tearDown()

runExperiments("wireless_phy_phy_", "172.16.0.1", "172.16.0.2")
