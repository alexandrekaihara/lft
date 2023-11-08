from experiment.pschedulerWrapper import Throughput, Rtt, Latency
from experiment.emu_emu_wireless import EmuEmuWireless
from experiment.emu_phy_wireless import EmuPhyWireless


'''
# Wireless emu-emu
testname = "wireless_emu_emu_"
sourceWirelessEmuEmu = "172.168.0.1"
targetWirelessEmuEmu = "172.168.0.2"
throughput.Source(sourceWirelessEmuEmu).Dest(targetWirelessEmuEmu).OutputFile(resultsPath, testname + "throughput_%n.json").mountCommand().run()
rtt.Source(sourceWirelessEmuEmu).Dest(targetWirelessEmuEmu).OutputFile(resultsPath, testname + "rtt_%n.json").mountCommand().run()
latency.Source(sourceWirelessEmuEmu).Dest(targetWirelessEmuEmu).OutputFile(resultsPath, testname + "latency_%n.json").mountCommand().run()

# Wireless phy-emu (does this make sense?)
testname = "wireless_phy_emu_"
sourceWiredEmuEmu = "172.168.0.1"
targetWiredEmuEmu = "172.168.0.2"
throughput.Source(sourceWiredEmuEmu).Dest(targetWiredEmuEmu).OutputFile(resultsPath, testname + "throughput_%n.json").mountCommand().run()
rtt.Source(sourceWiredEmuEmu).Dest(targetWiredEmuEmu).OutputFile(resultsPath, testname + "rtt_%n.json").mountCommand().run()
latency.Source(sourceWiredEmuEmu).Dest(targetWiredEmuEmu).OutputFile(resultsPath, testname + "latency_%n.json").mountCommand().run()

# Wireless phy-phy (does this make sense?)
testname = "wireless_phy_emu_"
sourceWiredEmuEmu = "172.168.0.1"
targetWiredEmuEmu = "172.168.0.2"
throughput.Source(sourceWiredEmuEmu).Dest(targetWiredEmuEmu).OutputFile(resultsPath, testname + "throughput_%n.json").mountCommand().run()
rtt.Source(sourceWiredEmuEmu).Dest(targetWiredEmuEmu).OutputFile(resultsPath, testname + "rtt_%n.json").mountCommand().run()
latency.Source(sourceWiredEmuEmu).Dest(targetWiredEmuEmu).OutputFile(resultsPath, testname + "latency_%n.json").mountCommand().run()
'''
