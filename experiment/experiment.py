from experiment.pschedulerWrapper import Throughput, Rtt, Latency


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
