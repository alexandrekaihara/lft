import matplotlib.pyplot as plt
from results.preprocess_throughput import Throughput
from results.preprocess_rtt import Rtt
from results.preprocess_latency import Latency
from experiment.constants import *
from scipy import stats
import numpy as np
from json import load
from glob import glob


def confidenceInterval(data, confidence=0.95):
    mean = np.mean(data)
    stderr = stats.sem(data)
    margin_of_error = stderr * stats.t.ppf((1 + confidence) / 2.0, len(data) - 1)
    lower_bound = mean - margin_of_error
    upper_bound = mean + margin_of_error
    return lower_bound, mean, upper_bound


def getPaths(path):
    return glob(path)


def flattenList(listOfLists):
    return [element for singleList in listOfLists for element in singleList ]


def loadThroughputData(path):
    throughput = Throughput()
    throughputPaths = getPaths(path)
    throughputJsons = [load(open(path)) for path in throughputPaths]
    return flattenList([throughput.getThroughputs(json) for json in throughputJsons])


def loadRttData(path):
    rtt = Rtt()
    rttPaths = getPaths(path)
    rttJsons = [load(open(path)) for path in rttPaths]
    return flattenList([rtt.getRTTs(json) for json in rttJsons])

    
def loadLatencyData(path):
    latency = Latency()
    latencyPaths = getPaths(path)
    latencyJsons = [load(open(path)) for path in latencyPaths]
    return flattenList([latency.getlatencys(json) for json in latencyJsons])


def simplePlot(emuEmu, emuPhy, phyPhy, experimentLabel):
    plt.plot(emuEmu, label='Emulated')
    plt.plot(emuPhy, label='Hybrid')
    plt.plot(phyPhy, label='Physical')

    plt.title(f'{experimentLabel} Data')

    plt.xlabel('Time')
    plt.ylabel(experimentLabel)

    plt.show()


def plotConfidenceInterval(ciEmuEmu, ciEmuPhy, ciPhyPhy, experimentLabel):
    plt.plot(ciEmuEmu, (0, 0),'ro-',color='green')
    plt.plot(ciEmuPhy, (1, 1),'ro-',color='yellow')
    plt.plot(ciPhyPhy, (2, 2),'ro-',color='red')

    plt.xlabel(f'Confidence Intervals for {experimentLabel}')
    plt.ylabel('Mean')
    plt.title(f'{experimentLabel} Confidence Intervals')

    plt.yticks(range(len(3)), ['Emulated Only', 'Hybrid', 'Physical Only'])

    plt.show()


####################### Load Data #######################
# Wired
## Throughput
wiredEmuEmuThroughputData = loadThroughputData(RESULTS_PATH + EMU_EMU_WIRED_PREFIX + THROUGHPUT_JSON_FORMAT_WILDCARD)
wiredEmuPhyThroughputData = loadThroughputData(RESULTS_PATH + EMU_PHY_WIRED_PREFIX + THROUGHPUT_JSON_FORMAT_WILDCARD)
wiredPhyPhyThroughputData = loadThroughputData(RESULTS_PATH + PHY_PHY_WIRED_PREFIX + THROUGHPUT_JSON_FORMAT_WILDCARD)

## RTT
wiredEmuEmuRttData = loadRttData(RESULTS_PATH + EMU_EMU_WIRED_PREFIX + RTT_JSON_FORMAT_WILDCARD)
wiredEmuPhyRttData = loadRttData(RESULTS_PATH + EMU_PHY_WIRED_PREFIX + RTT_JSON_FORMAT_WILDCARD)
wiredPhyPhyRttData = loadRttData(RESULTS_PATH + PHY_PHY_WIRED_PREFIX + RTT_JSON_FORMAT_WILDCARD)

## Latency
wiredEmuEmuLatencyData = loadLatencyData(RESULTS_PATH + EMU_EMU_WIRED_PREFIX + LATENCY_JSON_FORMAT_WILDCARD)
wiredEmuPhyLatencyData = loadLatencyData(RESULTS_PATH + EMU_PHY_WIRED_PREFIX + LATENCY_JSON_FORMAT_WILDCARD)
wiredPhyPhyLatencyData = loadLatencyData(RESULTS_PATH + PHY_PHY_WIRED_PREFIX + LATENCY_JSON_FORMAT_WILDCARD)

# Wireless
## Throughput
wirelessEmuEmuThroughputData = loadThroughputData(RESULTS_PATH + EMU_EMU_WIRELESS_PREFIX + THROUGHPUT_JSON_FORMAT_WILDCARD)
wirelessEmuPhyThroughputData = loadThroughputData(RESULTS_PATH + EMU_PHY_WIRELESS_PREFIX + THROUGHPUT_JSON_FORMAT_WILDCARD)
wirelessPhyPhyThroughputData = loadThroughputData(RESULTS_PATH + PHY_PHY_WIRELESS_PREFIX + THROUGHPUT_JSON_FORMAT_WILDCARD)

## RTT
wirelessEmuEmuRttData = loadRttData(RESULTS_PATH + EMU_EMU_WIRELESS_PREFIX + RTT_JSON_FORMAT_WILDCARD)
wirelessEmuPhyRttData = loadRttData(RESULTS_PATH + EMU_PHY_WIRELESS_PREFIX + RTT_JSON_FORMAT_WILDCARD)
wirelessPhyPhyRttData = loadRttData(RESULTS_PATH + PHY_PHY_WIRELESS_PREFIX + RTT_JSON_FORMAT_WILDCARD)

## Latency
wirelessEmuEmuLatencyData = loadLatencyData(RESULTS_PATH + EMU_EMU_WIRELESS_PREFIX + LATENCY_JSON_FORMAT_WILDCARD)
wirelessEmuPhyLatencyData = loadLatencyData(RESULTS_PATH + EMU_PHY_WIRELESS_PREFIX + LATENCY_JSON_FORMAT_WILDCARD)
wirelessPhyPhyLatencyData = loadLatencyData(RESULTS_PATH + PHY_PHY_WIRELESS_PREFIX + LATENCY_JSON_FORMAT_WILDCARD)


####################### Get Confidence Intervals #######################
# Wired
## Throughput
ciWiredEmuEmuThroughputData = confidenceInterval(wiredEmuEmuThroughputData)
ciWiredEmuPhyThroughputData = confidenceInterval(wiredEmuPhyThroughputData)
ciWiredPhyPhyThroughputData = confidenceInterval(wiredPhyPhyThroughputData)

## RTT
ciWiredEmuEmuRttData = confidenceInterval(wiredEmuEmuRttData)
ciWiredEmuPhyRttData = confidenceInterval(wiredEmuPhyRttData)
ciWiredPhyPhyRttData = confidenceInterval(wiredPhyPhyRttData)

## Latency
ciWiredEmuEmuLatencyData = confidenceInterval(wiredEmuEmuLatencyData)
ciWiredEmuPhyLatencyData = confidenceInterval(wiredEmuPhyLatencyData)
ciWiredPhyPhyLatencyData = confidenceInterval(wiredPhyPhyLatencyData)

# Wireless
## Throughput
ciWirelessEmuEmuThroughputData = confidenceInterval(wirelessEmuEmuThroughputData)
ciWirelessEmuPhyThroughputData = confidenceInterval(wirelessEmuPhyThroughputData)
ciWirelessPhyPhyThroughputData = confidenceInterval(wirelessPhyPhyThroughputData)

## RTT
ciWirelessEmuEmuRttData = confidenceInterval(wirelessEmuEmuRttData)
ciWirelessEmuPhyRttData = confidenceInterval(wirelessEmuPhyRttData)
ciWirelessPhyPhyRttData = confidenceInterval(wirelessPhyPhyRttData)

## Latency
ciWirelessEmuEmuLatencyData = confidenceInterval(wirelessEmuEmuLatencyData)
ciWirelessEmuPhyLatencyData = confidenceInterval(wirelessEmuPhyLatencyData)
ciWirelessPhyPhyLatencyData = confidenceInterval(wirelessPhyPhyLatencyData)


####################### Plots #######################
# Wired
# Throughput
simplePlot(wiredEmuEmuThroughputData, wiredEmuPhyLatencyData, wiredPhyPhyThroughputData, THROUGHPUT_EXPERIMENT_NAME)
plotConfidenceInterval(ciWiredEmuEmuThroughputData, ciWiredEmuPhyThroughputData, ciWiredPhyPhyThroughputData)

# RTT
simplePlot(wiredEmuEmuRttData, wiredEmuPhyLatencyData, wiredPhyPhyRttData, THROUGHPUT_EXPERIMENT_NAME)
plotConfidenceInterval(ciWiredEmuEmuRttData, ciWiredEmuPhyRttData, ciWiredPhyPhyRttData)

# Latency
simplePlot(wiredEmuEmuLatencyData, wiredEmuPhyLatencyData, wiredPhyPhyLatencyData, THROUGHPUT_EXPERIMENT_NAME)
plotConfidenceInterval(ciWiredEmuEmuLatencyData, ciWiredEmuPhyLatencyData, ciWiredPhyPhyLatencyData)