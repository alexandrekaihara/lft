import matplotlib.pyplot as plt
from results.preprocess_throughput import Throughput
from results.preprocess_rtt import Rtt
from results.preprocess_latency import Latency
from experiment.constants import *
from scipy import stats
import pandas as pd
import numpy as np
from json import load
from glob import glob
from statistics import mean


def confidenceInterval(data, confidence=0.95):
    mean = np.mean(data)
    stderr = np.std(data)
    return stats.norm.interval(alpha=confidence, loc=mean, scale=stderr) 

def clearOutliers(data):
    mean = np.mean(data)
    std = np.std(data)
    threshold = 3
    filteredData = []
    for i in data:
        z = (i-mean)/std
        if z < threshold:
            filteredData.append(i)
    return filteredData

def getPaths(path):
    paths = glob(path)
    print(f"Retrieved {len(paths)} from {path}:\n{paths}")
    return paths


def flattenList(listOfLists):
    return [element for singleList in listOfLists for element in singleList]


def loadJsons(jsonPaths):
    jsons = []
    successfulReadFiles = 0
    for path in jsonPaths:
        try:
            print(f"Loading {path}.")
            json = load(open(path))
            if (json != None and json['succeeded']):
                print(f"Loaded successfully file {path}")
                jsons.append(json)
                successfulReadFiles += 1
        except Exception as ex:
            print(f"Failed to load file {path} due to {ex}")
    print(f"Read successfully {successfulReadFiles}/{len(jsonPaths)}")
    return jsons


def extractMetricsFromJsons(jsons, keyName):
    successfulExtractions = 0
    metricsList = []
    print(f"Starting extracting {keyName} metrics from {len(jsons)} JSON files")
    for json in jsons:
        metrics = extractMetricsFromJson(json, keyName)
        if (metrics != None):
            metricsList.append(metrics)
            successfulExtractions += 1
    print(f"Extracted {keyName} successfully from {successfulExtractions}/{len(jsons)}")
    return metricsList


def extractMetricsFromJson(json, keyName):
    extractor = None
    if keyName == THROUGHPUT:
        extractor = Throughput()
    elif keyName == RTT:
        extractor = Rtt()
    elif (keyName == LATENCY):
        extractor = Latency()
    return extractor.get(json, keyName)


def loadData(path, keyName):
    print(f"Loading {THROUGHPUT} Data")
    filePaths = getPaths(path)
    jsons = loadJsons(filePaths)
    collectedMetricsList = extractMetricsFromJsons(jsons, keyName)
    print(collectedMetricsList)
    flatListValues = flattenList(collectedMetricsList)
    return clearOutliers(flatListValues)


def simplePlot(emuEmu, emuPhy, phyPhy, experimentLabel, mediumType):
    plt.plot(emuEmu, label='Emulated')
    plt.plot(emuPhy, label='Hybrid')
    plt.plot(phyPhy, label='Physical')
    plt.title(f'{experimentLabel} - {mediumType}')
    plt.xlabel('Data Points')
    plt.ylabel(experimentLabel)
    plt.legend()
    plt.show()


def plotConfidenceInterval(ciEmuEmu, ciEmuPhy, ciPhyPhy, experimentLabel, mediumType):
    plt.plot(ciEmuEmu, (0, 0),'ro-',color='green')
    plt.plot(ciEmuPhy, (1, 1),'ro-',color='yellow')
    plt.plot(ciPhyPhy, (2, 2),'ro-',color='red')
    plt.xlabel(f'Confidence Intervals for {experimentLabel} - {mediumType}')
    plt.ylabel('Mean')
    plt.title(f'{experimentLabel} Confidence Intervals')
    plt.yticks(range(3), ['Emulated Only', 'Hybrid', 'Physical Only'])
    plt.show()



####################### Load Data #######################
# Wired
## Throughput
wiredEmuEmuThroughputData = loadData(RESULTS_PATH + EMU_EMU_WIRED_PREFIX + THROUGHPUT_JSON_FORMAT_WILDCARD, THROUGHPUT)
wiredEmuPhyThroughputData = loadData(RESULTS_PATH + EMU_PHY_WIRED_PREFIX + THROUGHPUT_JSON_FORMAT_WILDCARD, THROUGHPUT)
wiredPhyPhyThroughputData = loadData(RESULTS_PATH + PHY_PHY_WIRED_PREFIX + THROUGHPUT_JSON_FORMAT_WILDCARD, THROUGHPUT)

## RTT
wiredEmuEmuRttData = loadData(RESULTS_PATH + EMU_EMU_WIRED_PREFIX + RTT_JSON_FORMAT_WILDCARD, RTT)
wiredEmuPhyRttData = loadData(RESULTS_PATH + EMU_PHY_WIRED_PREFIX + RTT_JSON_FORMAT_WILDCARD, RTT)
wiredPhyPhyRttData = loadData(RESULTS_PATH + PHY_PHY_WIRED_PREFIX + RTT_JSON_FORMAT_WILDCARD, RTT)

## Latency
wiredEmuEmuLatencyData = loadData(RESULTS_PATH + EMU_EMU_WIRED_PREFIX + LATENCY_JSON_FORMAT_WILDCARD, LATENCY)
wiredEmuPhyLatencyData = loadData(RESULTS_PATH + EMU_PHY_WIRED_PREFIX + LATENCY_JSON_FORMAT_WILDCARD, LATENCY)
wiredPhyPhyLatencyData = loadData(RESULTS_PATH + PHY_PHY_WIRED_PREFIX + LATENCY_JSON_FORMAT_WILDCARD, LATENCY)

# Wireless
## Throughput
wirelessEmuEmuThroughputData = loadData(RESULTS_PATH + EMU_EMU_WIRELESS_PREFIX + THROUGHPUT_JSON_FORMAT_WILDCARD, THROUGHPUT)
wirelessEmuPhyThroughputData = loadData(RESULTS_PATH + EMU_PHY_WIRELESS_PREFIX + THROUGHPUT_JSON_FORMAT_WILDCARD, THROUGHPUT)
wirelessPhyPhyThroughputData = loadData(RESULTS_PATH + PHY_PHY_WIRELESS_PREFIX + THROUGHPUT_JSON_FORMAT_WILDCARD, THROUGHPUT)

## RTT
wirelessEmuEmuRttData = loadData(RESULTS_PATH + EMU_EMU_WIRELESS_PREFIX + RTT_JSON_FORMAT_WILDCARD, RTT)
wirelessEmuPhyRttData = loadData(RESULTS_PATH + EMU_PHY_WIRELESS_PREFIX + RTT_JSON_FORMAT_WILDCARD, RTT)
wirelessPhyPhyRttData = loadData(RESULTS_PATH + PHY_PHY_WIRELESS_PREFIX + RTT_JSON_FORMAT_WILDCARD, RTT)

## Latency
wirelessEmuEmuLatencyData = loadData(RESULTS_PATH + EMU_EMU_WIRELESS_PREFIX + LATENCY_JSON_FORMAT_WILDCARD, LATENCY)
wirelessEmuPhyLatencyData = loadData(RESULTS_PATH + EMU_PHY_WIRELESS_PREFIX + LATENCY_JSON_FORMAT_WILDCARD, LATENCY)
wirelessPhyPhyLatencyData = loadData(RESULTS_PATH + PHY_PHY_WIRELESS_PREFIX + LATENCY_JSON_FORMAT_WILDCARD, LATENCY)


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
## Throughput
simplePlot(wiredEmuEmuThroughputData, wiredEmuPhyThroughputData, wiredPhyPhyThroughputData, THROUGHPUT_EXPERIMENT_NAME, WIRED)
plotConfidenceInterval(ciWiredEmuEmuThroughputData, ciWiredEmuPhyThroughputData, ciWiredPhyPhyThroughputData, THROUGHPUT_EXPERIMENT_NAME, WIRED)

## RTT
simplePlot(wiredEmuEmuRttData, wiredEmuPhyRttData, wiredPhyPhyRttData, RTT_EXPERIMENT_NAME, WIRED)
plotConfidenceInterval(ciWiredEmuEmuRttData, ciWiredEmuPhyRttData, ciWiredPhyPhyRttData, RTT_EXPERIMENT_NAME, WIRED)

## Latency
simplePlot(wiredEmuEmuLatencyData, wiredEmuPhyLatencyData, wiredPhyPhyLatencyData, LATENCY_EXPERIMENT_NAME, WIRED)
plotConfidenceInterval(ciWiredEmuEmuLatencyData, ciWiredEmuPhyLatencyData, ciWiredPhyPhyLatencyData, LATENCY_EXPERIMENT_NAME, WIRED)


# Wireless
## Throughput
simplePlot(wirelessEmuEmuLatencyData, wirelessEmuPhyThroughputData, wirelessPhyPhyThroughputData, THROUGHPUT_EXPERIMENT_NAME, WIRELESS)
plotConfidenceInterval(ciWirelessEmuEmuThroughputData, ciWirelessEmuPhyThroughputData, ciWirelessPhyPhyThroughputData, THROUGHPUT_EXPERIMENT_NAME, WIRELESS)

## RTT
simplePlot(wirelessEmuEmuRttData, wirelessEmuPhyRttData, wirelessPhyPhyRttData, RTT_EXPERIMENT_NAME, WIRELESS)
plotConfidenceInterval(ciWirelessEmuEmuRttData, ciWirelessEmuPhyRttData, ciWirelessPhyPhyRttData, RTT_EXPERIMENT_NAME, WIRELESS)

## Latency
simplePlot(wirelessEmuEmuLatencyData, wirelessEmuPhyLatencyData, wirelessPhyPhyLatencyData, LATENCY_EXPERIMENT_NAME, WIRELESS)
plotConfidenceInterval(ciWirelessEmuEmuLatencyData, ciWirelessEmuPhyLatencyData, ciWirelessPhyPhyLatencyData, LATENCY_EXPERIMENT_NAME, WIRELESS)



# set width of bars
barWidth = 0.25

# set heights of bars
emulated = [mean(wiredEmuEmuRttData), mean(wirelessEmuEmuRttData)]
hybrid = [mean(wiredEmuPhyRttData), 41300]#mean(wirelessEmuPhyRttData)
physical = [mean(wiredPhyPhyRttData), mean(wirelessPhyPhyRttData)]

# Set position of bar on X axis
r1 = np.arange(len(emulated))
r2 = [x + barWidth for x in r1]
r3 = [x + barWidth for x in r2]

# Make the plot
plt.bar(r1, emulated, color='#7f6d5f', width=barWidth, edgecolor='white', label='Fully Emulated')
plt.bar(r2, hybrid, color='#557f2d', width=barWidth, edgecolor='white', label='Hybrid')
plt.bar(r3, physical, color='#2d7f5e', width=barWidth, edgecolor='white', label='Fully Physical')

# Add xticks on the middle of the group bars
plt.xlabel('Medium', fontweight='bold')
plt.xticks([r + barWidth for r in range(len(emulated))], ['Wired', 'Wireless'])

# Create legend & Show graphic
plt.legend()
plt.show()



emulatedMean = mean(wiredEmuEmuThroughputData)
hybridMean = mean(wiredEmuPhyThroughputData)
physicalMean = mean(wiredPhyPhyThroughputData)
means = [emulatedMean, hybridMean, physicalMean]
errs = [ciWiredEmuEmuThroughputData[1] - emulatedMean, ciWiredEmuPhyThroughputData[1] - hybridMean, ciWiredPhyPhyThroughputData[1] - physicalMean]
smallest = min(min([wiredEmuEmuThroughputData, wiredEmuPhyThroughputData, wiredPhyPhyThroughputData]))
higher = max(max([wiredEmuEmuThroughputData, wiredEmuPhyThroughputData, wiredPhyPhyThroughputData]))
               
columns = ["Emulated Only", "Hybrid", "Physical Only"]
colors=["red", "green", "blue"]
plt.bar(range(len(columns)), means, 
        yerr=errs, align='center', alpha=0.5, color=colors, edgecolor='black', capsize=7)
plt.ylim(smallest, higher)
plt.xticks(range(len(columns)), columns)
plt.ylabel("Throughput (MBps)")
plt.title('Wired Experiment Throughput')
plt.show()
#https://python-graph-gallery.com/8-add-confidence-interval-on-barplot/