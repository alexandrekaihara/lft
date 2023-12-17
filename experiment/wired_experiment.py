from experiment.experiment import *
from experiment.emu_emu_wired import EmuEmuWired
from experiment.emu_phy_wired import EmuPhyWired


# wired emu-emu
emuEmu = EmuEmuWired()
emuEmu.setup()
runExperiments("wired_emu_emu_", "10.0.0.1", "10.0.0.2")
emuEmu.tearDown()

# wired phy-emu
emuPhy = EmuPhyWired()
emuPhy.setup()
runExperiments("wired_emu_phy_", "10.0.0.2", "192.168.10.1")
emuPhy.tearDown()

# wired phy-phy
runExperiments("wired_phy_phy_", "localhost", "192.168.10.1")
