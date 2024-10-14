from experiment.experiment import *
from experiment.emu_emu_wired import EmuEmuWired
from experiment.emu_phy_wired import EmuPhyWired


# wired emu-emu
emuEmu = EmuEmuWired()
emuEmu.setup()
runThroughput(EMU_EMU_WIRED_PREFIX, EMU_EMU_WIRED_H1_IP, EMU_EMU_WIRED_H2_IP)
runRTT(EMU_EMU_WIRED_PREFIX, EMU_EMU_WIRED_H1_IP, EMU_EMU_WIRED_H2_IP)
runLatency(EMU_EMU_WIRED_PREFIX, EMU_EMU_WIRED_H1_IP, EMU_EMU_WIRED_H2_IP)
emuEmu.tearDown()

# wired phy-emu
emuPhy = EmuPhyWired()
emuPhy.setup()
runThroughput(EMU_PHY_WIRED_PREFIX, EMU_PHY_WIRED_H1_IP, EMU_PHY_WIRED_H2_IP)
runRTT(EMU_PHY_WIRED_PREFIX, EMU_PHY_WIRED_H1_IP, EMU_PHY_WIRED_H2_IP)
runLatency(EMU_PHY_WIRED_PREFIX, EMU_PHY_WIRED_H1_IP, EMU_PHY_WIRED_H2_IP)
emuPhy.tearDown()

# wired phy-phy
runThroughput(PHY_PHY_WIRED_PREFIX, PHY_PHY_WIRED_H1_IP, PHY_PHY_WIRED_H2_IP)
runRTT(PHY_PHY_WIRED_PREFIX, PHY_PHY_WIRED_H1_IP, PHY_PHY_WIRED_H2_IP)
runLatency(PHY_PHY_WIRED_PREFIX, PHY_PHY_WIRED_H1_IP, PHY_PHY_WIRED_H2_IP)