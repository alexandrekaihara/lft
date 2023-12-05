from experiment.pschedulerWrapper import Throughput, Rtt, Latency
from experiment.emu_emu_wired import EmuEmuWired
from experiment.emu_phy_wired import EmuPhyWired

interval = "PT15M"
maxRuns = 10
resultsPath = "results/data/"

throughput = Throughput().Format("json").MaxRuns(maxRuns).Repeat(interval)
rtt = Rtt().Format("json").MaxRuns(25).Repeat("PT3M")
latency = Latency().Format("json").MaxRuns(maxRuns).Repeat(interval)

def runExperiments(testname, sourceIp, targetIp):
        throughput.Source(sourceIp)\
                .Dest(targetIp)\
                .OutputFile(resultsPath, testname + "throughput_%n.json")\
                .ThroughputDuration(60)\
                .mountCommand()
        rtt.Source(sourceIp)\
                .Dest(targetIp)\
                .OutputFile(resultsPath, testname + "rtt_%n.json")\
                .Count(60)\
                .mountCommand()
        latency.Source(sourceIp)\
                .Dest(targetIp)\
                .OutputRaw()\
                .OutputFile(resultsPath, testname + "latency_%n.json")\
                .PacketCount(60)\
                .mountCommand()
        print("Running now command " + throughput.command)
        throughput.run()
        print("Running now command " + rtt.command)
        rtt.run()
        print("Running now command " + latency.command)
        latency.run()


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
