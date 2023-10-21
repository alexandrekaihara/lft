from experiment.pschedulerWrapper import Throughput, Rtt, Latency
from experiment.emu_emu_wired import EmuEmuWired
from experiment.emu_phy_wired import EmuPhyWired


def runExperiments(sourceIp, targetIp):
        throughput.Source(sourceIp)\
                .Dest(targetIp)\
                .OutputFile(resultsPath, testname + "throughput_%n.json")\
                .mountCommand()\
                .run()
        rtt.Source(sourceIp)\
                .Dest(targetIp)\
                .OutputFile(resultsPath, testname + "rtt_%n.json")\
                .mountCommand()\
                .run()
        latency.Source(sourceIp)\
                .Dest(targetIp)\
                .OutputFile(resultsPath, testname + "latency_%n.json")\
                .mountCommand()\
                .run()


testDuration = "PT1M"
maxRuns = 5
resultsPath = "experiment/results/"

throughput = Throughput().Format("json").MaxRuns(maxRuns, testDuration)
rtt = Rtt().Format("json").MaxRuns(maxRuns, testDuration)
latency = Latency().Format("json").MaxRuns(maxRuns, testDuration)


# wired emu-emu
emuEmu = EmuEmuWired()
emuEmu.setup()
testname = "wired_emu_emu_"
sourceWiredEmuEmu = "10.0.0.1"
targetWiredEmuEmu = "10.0.0.2"
runExperiments(sourceWiredEmuEmu, targetWiredEmuEmu)
emuEmu.tearDown()

# wired phy-emu
emuPhy = EmuPhyWired()
emuPhy.setup()
testname = "wired_emu_phy_"
sourceWiredPhyEmu = "10.0.0.2"
targetWiredPhyEmu = "192.168.10.1"
throughput.Source(sourceWiredPhyEmu).Dest(targetWiredPhyEmu).OutputFile(resultsPath, testname + "throughput_%n.json").mountCommand().run()
rtt.Source(sourceWiredPhyEmu).Dest(targetWiredPhyEmu).OutputFile(resultsPath, testname + "rtt_%n.json").mountCommand().run()
latency.Source(sourceWiredPhyEmu).Dest(targetWiredPhyEmu).OutputFile(resultsPath, testname + "latency_%n.json").mountCommand().run()
emuPhy.tearDown()

# wired phy-phy
testname = "wired_phy_phy_"
targetWiredPhyPhy = "192.168.10.1"
throughput.Dest(targetWiredPhyPhy).OutputFile(resultsPath, testname + "throughput_%n.json").mountCommand().run()
rtt.Dest(targetWiredPhyPhy).OutputFile(resultsPath, testname + "rtt_%n.json").mountCommand().run()
latency.Dest(targetWiredPhyPhy).OutputFile(resultsPath, testname + "latency_%n.json").mountCommand().run()


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
