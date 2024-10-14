from experiment.pschedulerWrapper import Throughput, Rtt, Latency
from experiment.constants import *


throughput = Throughput().Format(PERFSONAR_JSON_OUTPUT_FORMAT).MaxRuns(MAX_RUNS).Repeat(INTERVAL)
rtt = Rtt().Format(PERFSONAR_JSON_OUTPUT_FORMAT).MaxRuns(25).Repeat(REPEAT_INTERVAL)
latency = Latency().Format(PERFSONAR_JSON_OUTPUT_FORMAT).MaxRuns(MAX_RUNS).Repeat(INTERVAL)


def runThroughput(testname, sourceIp, targetIp):
        throughput.Source(sourceIp)\
                .Dest(targetIp)\
                .OutputFile(RESULTS_PATH, testname + THROUGHPUT_JSON_FORMAT)\
                .ThroughputDuration(60)\
                .mountCommand()
        print("Running now command " + throughput.command)
        throughput.run()


def runRTT(testname, sourceIp, targetIp):
        rtt.Source(sourceIp)\
                .Dest(targetIp)\
                .OutputFile(RESULTS_PATH, testname + RTT_JSON_FORMAT)\
                .Count(60)\
                .mountCommand()
        print("Running now command " + rtt.command)
        rtt.run()


def runLatency(testname, sourceIp, targetIp):
        latency.Source(sourceIp)\
                .Dest(targetIp)\
                .OutputRaw()\
                .OutputFile(RESULTS_PATH, testname + LATENCY_JSON_FORMAT)\
                .PacketCount(60)\
                .mountCommand()
        print("Running now command " + latency.command)
        latency.run()
        
