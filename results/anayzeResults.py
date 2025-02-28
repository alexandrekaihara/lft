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
from statistics import mean, median
from matplotlib import use
from itertools import combinations

use("TkAgg")

def confidenceInterval(data, confidence=0.99):
    mean = np.mean(data)
    stderr = stats.sem(data) # usar o erro padrao
    return stats.norm.interval(confidence=confidence, loc=mean, scale=stderr) 

def clearOutliers(data):
    npData = np.array(data)
    zScores = stats.zscore(data)
    return npData[[abs(z) < 3 for z in zScores]]

    '''mean = np.mean(data)
    std = np.std(data)
    threshold = 3
    filteredData = []
    for i in data:
        z = abs((i-mean)/std)
        if z < threshold:
            filteredData.append(i)
    return filteredData'''

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

def loadCustomThroughputJson(path):
    jsons = []
    paths = glob(path)
    for path in paths:
        json = load(open(path))
        jsons.append(json)
    return flattenList(jsons)

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


def simplePlot(emuEmu, emuPhy, phyPhy, experimentLabel, mediumType, unitOfMeasure):
    plt.plot(emuEmu, label='Emulated', color=EMU_EMU_PLOT_COLOR)
    plt.plot(emuPhy, label='Hybrid', color=EMU_PHY_PLOT_COLOR)
    plt.plot(phyPhy, label='Physical', color=PHY_PHY_PLOT_COLOR)
    plt.title(f'{experimentLabel} - {mediumType}')
    plt.xlabel('Data Points')
    plt.ylabel(f"{experimentLabel} ({unitOfMeasure})")
    plt.legend()
    plt.show()


def plotConfidenceInterval(ciEmuEmu, ciEmuPhy, ciPhyPhy, experimentLabel, mediumType):
    plt.plot(ciEmuEmu, (0, 0),'ro-')
    plt.plot(ciEmuPhy, (1, 1),'ro-')
    plt.plot(ciPhyPhy, (2, 2),'ro-')
    plt.xlabel(f'Confidence Intervals for {experimentLabel} - {mediumType}')
    plt.ylabel('Mean')
    plt.title(f'{experimentLabel} Confidence Intervals')
    plt.yticks(range(3), ['Emulated Only', 'Hybrid', 'Physical Only'])
    plt.show()


def plotBars(emuEmu, ciEmuEmu, emuPhy, ciEmuPhy, phyPhy, ciPhyPhy, experimentName, medium, unitOfMeasure):
    if (len(emuEmu) == 0):
        emuEmu = [0]
    if (len(emuPhy) == 0):
        emuPhy = [0]
    if (len(phyPhy) == 0):
        phyPhy = [0]
    if (ciEmuEmu == None):
        ciEmuEmu = (0,0)
    if (ciEmuPhy == None):
        ciEmuPhy = (0,0)
    if (ciPhyPhy == None):
        ciPhyPhy = (0,0)
    
    emulated_mean = mean(emuEmu)
    hybrid_mean = mean(emuPhy)
    physical_mean = mean(phyPhy)
    
    means = [emulated_mean, hybrid_mean, physical_mean]
    errs = [ciEmuEmu[1] - emulated_mean, ciEmuPhy[1] - hybrid_mean, ciPhyPhy[1] - physical_mean]
    
    higher = max([max(emuEmu), max(emuPhy), max(phyPhy)])
    
    columns = ["Emulated Only", "Hybrid", "Physical Only"]
    colors = [EMU_EMU_PLOT_COLOR, EMU_PHY_PLOT_COLOR, PHY_PHY_PLOT_COLOR]
    
    plt.bar(range(len(columns)), means, yerr=errs, align='center', alpha=0.5, color=colors, edgecolor='black', capsize=7)
    
    plt.ylim(0, higher*1.1)
    plt.yticks(fontsize=12)
    plt.xticks(range(len(columns)), columns, fontsize=12)
    plt.ylabel(f"{experimentName} ({unitOfMeasure})", fontsize=14)
    plt.title(f'{medium} Experiment {experimentName}', fontsize=16)
    plt.show()


def minLen(listOfLists):
    return min([len(l) for l in listOfLists])


def plotToolComparison(lftValues, lftErr, mnValues, mnErr, title, unitOfMeasure):
    barWidth = 0.25
    r1 = np.arange(len(lftValues))
    r2 = [x + barWidth for x in r1]
    plt.title(title, fontsize=18)
    plt.bar(r1, lftValues, color='#7f6d5f', width=barWidth, edgecolor='white', label='LFT', yerr=lftErr, capsize=3)
    plt.bar(r2, mnValues, color='#557f2d', width=barWidth, edgecolor='white', label='Mininet-WIFI (Containernet)', yerr=mnErr, capsize=3)
    plt.yticks(fontsize=14)
    plt.xticks([r + barWidth for r in range(len(lftValues))], ['1', '4', '16', '64', '256'], fontsize=14)
    plt.xlabel('Number of Nodes', fontsize=16)
    plt.ylabel(f"{title} ({unitOfMeasure})", fontsize=16)
    plt.legend(fontsize=14)
    plt.show()


def boxPlot(data, title, x_labels, y_axis_title, x_axis_title):
    plt.boxplot(data)
    plt.title(title, fontsize=18)
    plt.ylabel(y_axis_title, fontsize=16)
    plt.xlabel(x_axis_title, fontsize=16)
    plt.xticks(ticks=range(1, len(x_labels) + 1), labels=x_labels, fontsize=14)
    plt.yticks(fontsize=14)
    plt.show()

def deviation(first, second):
    return (abs(first - second)/mean([first, second]))*100


def plotBarsSubplots(data1, data2, experimentNames, medium, unitOfMeasures, titles):
    fig, axes = plt.subplots(1, 2, figsize=(12, 6))
    
    for i, data in enumerate([data1, data2]):
        emuEmu, ciEmuEmu, emuPhy, ciEmuPhy, phyPhy, ciPhyPhy = data
        
        emulated_mean = mean(emuEmu)
        hybrid_mean = mean(emuPhy)
        physical_mean = mean(phyPhy)
        
        means = [emulated_mean, hybrid_mean, physical_mean]
        errs = [ciEmuEmu[1] - emulated_mean, ciEmuPhy[1] - hybrid_mean, ciPhyPhy[1] - physical_mean]
        
        higher = max([max(emuEmu), max(emuPhy), max(phyPhy)])
        
        columns = ["Emulated Only", "Hybrid", "Physical Only"]
        colors = [EMU_EMU_PLOT_COLOR, EMU_PHY_PLOT_COLOR, PHY_PHY_PLOT_COLOR]
        
        axes[i].bar(range(len(columns)), means, yerr=errs, align='center', alpha=0.5, color=colors, edgecolor='black', capsize=7)
        axes[i].set_ylim(0, higher * 1.1)
        #axes[i].set_yticks(fontsize=12)
        #axes[i].set_xticks(range(len(columns)))
        axes[i].set_xticklabels(columns, fontsize=12)
        axes[i].set_ylabel(f"{experimentNames[i]} ({unitOfMeasures[i]})", fontsize=14)
        axes[i].set_title(titles[i], fontsize=16)
    
    fig.suptitle(f'{medium} Experiments', fontsize=18)
    plt.tight_layout()
    plt.show()

def boxPlotSubplots(data1, data2, titles, x_labels, y_axis_titles, x_axis_titles):
    fig, axes = plt.subplots(1, 2, figsize=(12, 6))
    
    for i, data in enumerate([data1, data2]):
        axes[i].boxplot(data)
        axes[i].set_title(titles[i], fontsize=18)
        axes[i].set_ylabel(y_axis_titles[i], fontsize=16)
        axes[i].set_xlabel(x_axis_titles[i], fontsize=16)
        axes[i].set_xticks(ticks=range(1, len(x_labels) + 1))
        axes[i].set_xticklabels(x_labels, fontsize=14)
        axes[i].tick_params(axis='y', labelsize=14)
    
    plt.tight_layout()
    plt.show()

        
####################### Load Data #######################
# Wired
## Throughput
wiredEmuEmuThroughputData = loadData(RESULTS_PATH + EMU_EMU_WIRED_PREFIX + THROUGHPUT_JSON_FORMAT_WILDCARD, THROUGHPUT)
wiredEmuPhyThroughputData = loadData(RESULTS_PATH + EMU_PHY_WIRED_PREFIX + THROUGHPUT_JSON_FORMAT_WILDCARD, THROUGHPUT)
wiredPhyPhyThroughputData = loadData(RESULTS_PATH + PHY_PHY_WIRED_PREFIX + THROUGHPUT_JSON_FORMAT_WILDCARD, THROUGHPUT)

minimunLength = minLen([wiredEmuEmuThroughputData, wiredEmuPhyThroughputData, wiredPhyPhyThroughputData])
wiredEmuEmuThroughputData = wiredEmuEmuThroughputData[:minimunLength]
wiredEmuPhyThroughputData = wiredEmuPhyThroughputData[:minimunLength]
wiredPhyPhyThroughputData = wiredPhyPhyThroughputData[:minimunLength]

## RTT
wiredEmuEmuRttData = loadData(RESULTS_PATH + EMU_EMU_WIRED_PREFIX + RTT_JSON_FORMAT_WILDCARD, RTT)
wiredEmuPhyRttData = loadData(RESULTS_PATH + EMU_PHY_WIRED_PREFIX + RTT_JSON_FORMAT_WILDCARD, RTT)
wiredPhyPhyRttData = loadData(RESULTS_PATH + PHY_PHY_WIRED_PREFIX + RTT_JSON_FORMAT_WILDCARD, RTT)

minimunLength = minLen([wiredEmuEmuRttData, wiredEmuPhyRttData, wiredPhyPhyRttData])
wiredEmuEmuRttData = wiredEmuEmuRttData[:minimunLength]
wiredEmuPhyRttData = wiredEmuPhyRttData[:minimunLength]
wiredPhyPhyRttData = wiredPhyPhyRttData[:minimunLength]

## Latency
wiredEmuEmuLatencyData = loadData(RESULTS_PATH + EMU_EMU_WIRED_PREFIX + LATENCY_JSON_FORMAT_WILDCARD, LATENCY)
wiredEmuPhyLatencyData = loadData(RESULTS_PATH + EMU_PHY_WIRED_PREFIX + LATENCY_JSON_FORMAT_WILDCARD, LATENCY)
wiredPhyPhyLatencyData = loadData(RESULTS_PATH + PHY_PHY_WIRED_PREFIX + LATENCY_JSON_FORMAT_WILDCARD, LATENCY)

minimunLength = minLen([wiredEmuEmuLatencyData, wiredEmuPhyLatencyData, wiredPhyPhyLatencyData])
wiredEmuEmuLatencyData = wiredEmuEmuLatencyData[:minimunLength]
wiredEmuPhyLatencyData = wiredEmuPhyLatencyData[:minimunLength]
wiredPhyPhyLatencyData = wiredPhyPhyLatencyData[:minimunLength]

# Wireless
## Throughput
wirelessEmuEmuThroughputData = loadData(RESULTS_PATH + EMU_EMU_WIRELESS_PREFIX + THROUGHPUT_JSON_FORMAT_WILDCARD, THROUGHPUT)
wirelessEmuPhyThroughputData = loadCustomThroughputJson(RESULTS_PATH + "wireless_emu_phy_throughput_manual*.json") # loadData(RESULTS_PATH + EMU_PHY_WIRELESS_PREFIX + THROUGHPUT_JSON_FORMAT_WILDCARD, THROUGHPUT)
wirelessPhyPhyThroughputData = loadData(RESULTS_PATH + PHY_PHY_WIRELESS_PREFIX + THROUGHPUT_JSON_FORMAT_WILDCARD, THROUGHPUT)

minimunLength = minLen([wirelessEmuEmuThroughputData, wirelessEmuPhyThroughputData, wirelessPhyPhyThroughputData])
wirelessEmuEmuThroughputData = wirelessEmuEmuThroughputData[:minimunLength]
wirelessEmuPhyThroughputData = wirelessEmuPhyThroughputData[:minimunLength]
wirelessPhyPhyThroughputData = wirelessPhyPhyThroughputData[:minimunLength]

## RTT
wirelessEmuEmuRttData = loadData(RESULTS_PATH + EMU_EMU_WIRELESS_PREFIX + RTT_JSON_FORMAT_WILDCARD, RTT)
wirelessEmuPhyRttData = loadData(RESULTS_PATH + EMU_PHY_WIRELESS_PREFIX + RTT_JSON_FORMAT_WILDCARD, RTT)
wirelessPhyPhyRttData = loadData(RESULTS_PATH + PHY_PHY_WIRELESS_PREFIX + RTT_JSON_FORMAT_WILDCARD, RTT)

minimunLength = minLen([wirelessEmuEmuRttData, wirelessEmuPhyRttData, wirelessPhyPhyRttData])
wirelessEmuEmuRttData = wirelessEmuEmuRttData[:minimunLength]
wirelessEmuPhyRttData = wirelessEmuPhyRttData[:minimunLength]
wirelessPhyPhyRttData = wirelessPhyPhyRttData[:minimunLength]

## Latency
wirelessEmuEmuLatencyData = loadData(RESULTS_PATH + EMU_EMU_WIRELESS_PREFIX + LATENCY_JSON_FORMAT_WILDCARD, LATENCY)
wirelessEmuPhyLatencyData = loadData(RESULTS_PATH + EMU_PHY_WIRELESS_PREFIX + LATENCY_JSON_FORMAT_WILDCARD, LATENCY)
wirelessPhyPhyLatencyData = loadData(RESULTS_PATH + PHY_PHY_WIRELESS_PREFIX + LATENCY_JSON_FORMAT_WILDCARD, LATENCY)

minimunLength = minLen([wirelessEmuEmuLatencyData, wirelessEmuPhyLatencyData, wirelessPhyPhyLatencyData])
wirelessEmuEmuLatencyData = wirelessEmuEmuLatencyData[:minimunLength]
wirelessEmuPhyLatencyData = wirelessEmuPhyLatencyData[:minimunLength]
wirelessPhyPhyLatencyData = wirelessPhyPhyLatencyData[:minimunLength]

# Comparison
## Deployment Time
lftDeployTimeDf = pd.read_csv("results/data/deployLftTime.csv")
mnDeployTimeDf = pd.read_csv("results/data/deployMnTime.csv")

lftDeployTime1 = list(lftDeployTimeDf['1'])
lftDeployTime4 = list(lftDeployTimeDf['4'])
lftDeployTime16 = list(lftDeployTimeDf['16'])
lftDeployTime64 = list(lftDeployTimeDf['64'])
lftDeployTime256 = list(lftDeployTimeDf['256'])

mnDeployTime1 = list(mnDeployTimeDf['1'])
mnDeployTime4 = list(mnDeployTimeDf['4'])
mnDeployTime16 = list(mnDeployTimeDf['16'])
mnDeployTime64 = list(mnDeployTimeDf['64'])
mnDeployTime256 = list(mnDeployTimeDf['256'])

lftDeploymentValues = [mean(lftDeployTime1), mean(lftDeployTime4), mean(lftDeployTime16), mean(lftDeployTime64), mean(lftDeployTime256)]
mininetDeploymentValues = [mean(mnDeployTime1), mean(mnDeployTime4), mean(mnDeployTime16), mean(mnDeployTime64), mean(mnDeployTime256)]

## Undeployment Time
lftUndeployTimeDf = pd.read_csv("results/data/undeployLftTime.csv")
mnUndeployTimeDf = pd.read_csv("results/data/undeployMnTime.csv")

lftUndeployTime1 = list(lftUndeployTimeDf['1'])
lftUndeployTime4 = list(lftUndeployTimeDf['4'])
lftUndeployTime16 = list(lftUndeployTimeDf['16'])
lftUndeployTime64 = list(lftUndeployTimeDf['64'])
lftUndeployTime256 = list(lftUndeployTimeDf['256'])

mnUndeployTime1 = list(mnUndeployTimeDf['1'])
mnUndeployTime4 = list(mnUndeployTimeDf['4'])
mnUndeployTime16 = list(mnUndeployTimeDf['16'])
mnUndeployTime64 = list(mnUndeployTimeDf['64'])
mnUndeployTime256 = list(mnUndeployTimeDf['256'])

lftUndeploymentValues = [mean(lftUndeployTime1), mean(lftUndeployTime4), mean(lftUndeployTime16), mean(lftUndeployTime64), mean(lftUndeployTime256)]
mininetUndeploymentValues = [mean(mnUndeployTime1), mean(mnUndeployTime4), mean(mnUndeployTime16), mean(mnUndeployTime64), mean(mnUndeployTime256)]

## Memory Consumption
lftDeployMemDf = pd.read_csv("results/data/deployLftMem.csv")
mnDeployMemDf = pd.read_csv("results/data/deployMnMem.csv")

lftDeployMem1 = list(lftDeployMemDf['1']/1000000)
lftDeployMem4 = list(lftDeployMemDf['4']/1000000)
lftDeployMem16 = list(lftDeployMemDf['16']/1000000)
lftDeployMem64 = list(lftDeployMemDf['64']/1000000)
lftDeployMem256 = list(lftDeployMemDf['256']/1000000)

mnDeployMem1 = list(mnDeployMemDf['1']/1000000)
mnDeployMem4 = list(mnDeployMemDf['4']/1000000)
mnDeployMem16 = list(mnDeployMemDf['16']/1000000)
mnDeployMem64 = list(mnDeployMemDf['64']/1000000)
mnDeployMem256 = list(mnDeployMemDf['256']/1000000)

lftDeploymentMemValues = [mean(lftDeployMem1), mean(lftDeployMem4), mean(lftDeployMem16), mean(lftDeployMem64), mean(lftDeployMem256)]
mininetDeploymentMemValues = [mean(mnDeployMem1), mean(mnDeployMem4), mean(mnDeployMem16), mean(mnDeployMem64), mean(mnDeployMem256)]


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

# LFT vs Mininet-WIFI
## LFT
### Deployment Time
errLftDeployTime1  = confidenceInterval(lftDeployTime1)[1] - mean(lftDeployTime1)
errLftDeployTime4  = confidenceInterval(lftDeployTime4)[1] - mean(lftDeployTime4)
errLftDeployTime16  = confidenceInterval(lftDeployTime16)[1] - mean(lftDeployTime16)
errLftDeployTime64  = confidenceInterval(lftDeployTime64)[1] - mean(lftDeployTime64)
errLftDeployTime256  = confidenceInterval(lftDeployTime256)[1] - mean(lftDeployTime256)

errLftDeployTime = [errLftDeployTime1, errLftDeployTime4, errLftDeployTime16, errLftDeployTime64, errLftDeployTime256]

### Undeployment Time
errLftUndeployTime1  = confidenceInterval(lftUndeployTime1)[1] - mean(lftUndeployTime1)
errLftUndeployTime4  = confidenceInterval(lftUndeployTime4)[1] - mean(lftUndeployTime4)
errLftUndeployTime16  = confidenceInterval(lftUndeployTime16)[1] - mean(lftUndeployTime16)
errLftUndeployTime64  = confidenceInterval(lftUndeployTime64)[1] - mean(lftUndeployTime64)
errLftUndeployTime256  = confidenceInterval(lftUndeployTime256)[1] - mean(lftUndeployTime256)

errLftUndeployTime = [errLftUndeployTime1, errLftUndeployTime4, errLftUndeployTime16, errLftUndeployTime64, errLftUndeployTime256]

## Memory Consumption
errLftDeployMem1  = confidenceInterval(lftDeployMem1)[1] - mean(lftDeployMem1)
errLftDeployMem4  = confidenceInterval(lftDeployMem4)[1] - mean(lftDeployMem4)
errLftDeployMem16  = confidenceInterval(lftDeployMem16)[1] - mean(lftDeployMem16)
errLftDeployMem64  = confidenceInterval(lftDeployMem64)[1] - mean(lftDeployMem64)
errLftDeployMem256  = confidenceInterval(lftDeployMem256)[1] - mean(lftDeployMem256)

errLftDeployMem = [errLftDeployMem1, errLftDeployMem4, errLftDeployMem16, errLftDeployMem64, errLftDeployMem256]

## Mininet
### Deployment Time
errMnDeployTime1  = confidenceInterval(mnDeployTime1)[1] - mean(mnDeployTime1)
errMnDeployTime4  = confidenceInterval(mnDeployTime4)[1] - mean(mnDeployTime4)
errMnDeployTime16  = confidenceInterval(mnDeployTime16)[1] - mean(mnDeployTime16)
errMnDeployTime64  = confidenceInterval(mnDeployTime64)[1] - mean(mnDeployTime64)
errMnDeployTime256  = confidenceInterval(mnDeployTime256)[1] - mean(mnDeployTime256)

errMnDeployTime = [errMnDeployTime1, errMnDeployTime4, errMnDeployTime16, errMnDeployTime64, errMnDeployTime256]

### Undeployment Time
errMnUndeployTime1  = confidenceInterval(mnUndeployTime1)[1] - mean(mnUndeployTime1)
errMnUndeployTime4  = confidenceInterval(mnUndeployTime4)[1] - mean(mnUndeployTime4)
errMnUndeployTime16  = confidenceInterval(mnUndeployTime16)[1] - mean(mnUndeployTime16)
errMnUndeployTime64  = confidenceInterval(mnUndeployTime64)[1] - mean(mnUndeployTime64)
errMnUndeployTime256  = confidenceInterval(mnUndeployTime256)[1] - mean(mnUndeployTime256)

errMnUndeployTime = [errMnUndeployTime1, errMnUndeployTime4, errMnUndeployTime16, errMnUndeployTime64, errMnUndeployTime256]

## Memory Consumption
errMnDeployMem1  = confidenceInterval(mnDeployMem1)[1] - mean(mnDeployMem1)
errMnDeployMem4  = confidenceInterval(mnDeployMem4)[1] - mean(mnDeployMem4)
errMnDeployMem16  = confidenceInterval(mnDeployMem16)[1] - mean(mnDeployMem16)
errMnDeployMem64  = confidenceInterval(mnDeployMem64)[1] - mean(mnDeployMem64)
errMnDeployMem256  = confidenceInterval(mnDeployMem256)[1] - mean(mnDeployMem256)

errMnDeployMem = [errMnDeployMem1, errMnDeployMem4, errMnDeployMem16, errMnDeployMem64, errMnDeployMem256]



####################### Plots #######################
# Wired
## Throughput
simplePlot(wiredEmuEmuThroughputData[:minimunLength], wiredEmuPhyThroughputData[:minimunLength], wiredPhyPhyThroughputData[:minimunLength], THROUGHPUT_EXPERIMENT_NAME, WIRED, THROUGHPUT_UNIT_OF_MEASURE)
#plotConfidenceInterval(ciWiredEmuEmuThroughputData, ciWiredEmuPhyThroughputData, ciWiredPhyPhyThroughputData, THROUGHPUT_EXPERIMENT_NAME, WIRED)
plotBars(wiredEmuEmuThroughputData, ciWiredEmuEmuThroughputData, wiredEmuPhyThroughputData, ciWiredEmuPhyThroughputData, wiredPhyPhyThroughputData, ciWiredPhyPhyThroughputData, THROUGHPUT_EXPERIMENT_NAME, WIRED, THROUGHPUT_UNIT_OF_MEASURE)
boxPlot([wiredEmuEmuThroughputData, wiredEmuPhyThroughputData, wiredPhyPhyThroughputData], f"{WIRED} {THROUGHPUT_EXPERIMENT_NAME}", [EMULATED, HYBRID, PHYSICAL], f"{THROUGHPUT_EXPERIMENT_NAME} ({THROUGHPUT_UNIT_OF_MEASURE})", "Peer Types")
print(f"Wired Throughput Deviation Emulated to Physical: {deviation(median(wiredEmuEmuThroughputData), median(wiredPhyPhyThroughputData))}")
print(f"Wired Throughput Deviation Emulated to Physical: {deviation(median(wiredEmuPhyThroughputData), median(wiredPhyPhyThroughputData))}")

## RTT
minimunLength = minLen([wiredEmuEmuRttData, wiredEmuPhyRttData, wiredPhyPhyRttData])
simplePlot(wiredEmuEmuRttData[:minimunLength], wiredEmuPhyRttData[:minimunLength], wiredPhyPhyRttData[:minimunLength], RTT_EXPERIMENT_NAME, WIRED, RTT_UNIT_OF_MEASURE)
#plotConfidenceInterval(ciWiredEmuEmuRttData, ciWiredEmuPhyRttData, ciWiredPhyPhyRttData, RTT_EXPERIMENT_NAME, WIRED)
plotBars(wiredEmuEmuRttData, ciWiredEmuEmuRttData, wiredEmuPhyRttData, ciWiredEmuPhyRttData, wiredPhyPhyRttData, ciWiredPhyPhyRttData, RTT_EXPERIMENT_NAME, WIRED, RTT_UNIT_OF_MEASURE)
boxPlot([wiredEmuEmuRttData, wiredEmuPhyRttData, wiredPhyPhyRttData], f"{WIRED} {RTT_EXPERIMENT_NAME}", [EMULATED, HYBRID, PHYSICAL], f"{RTT_EXPERIMENT_NAME} ({RTT_UNIT_OF_MEASURE})", "Peer Types")
print(f"Wired Rtt Deviation Emulated to Physical: {deviation(median(wiredEmuEmuRttData), median(wiredPhyPhyRttData))}")
print(f"Wired Rtt Deviation Emulated to Physical: {deviation(median(wiredEmuPhyRttData), median(wiredPhyPhyRttData))}")

## Latency
simplePlot(wiredEmuEmuLatencyData, wiredEmuPhyLatencyData, wiredPhyPhyLatencyData, LATENCY_EXPERIMENT_NAME, WIRED, LATENCY_UNIT_OF_MEASURE)
#plotConfidenceInterval(ciWiredEmuEmuLatencyData, ciWiredEmuPhyLatencyData, ciWiredPhyPhyLatencyData, LATENCY_EXPERIMENT_NAME, WIRED)
plotBars(wiredEmuEmuLatencyData, ciWiredEmuEmuLatencyData, wiredEmuPhyLatencyData, ciWiredEmuPhyLatencyData, wiredPhyPhyLatencyData, ciWiredPhyPhyLatencyData, LATENCY_EXPERIMENT_NAME, WIRED, LATENCY_UNIT_OF_MEASURE)
boxPlot([wiredEmuEmuLatencyData, wiredEmuPhyLatencyData, wiredPhyPhyLatencyData], f"{WIRED} {LATENCY_EXPERIMENT_NAME}", [EMULATED, HYBRID, PHYSICAL], f"{LATENCY_EXPERIMENT_NAME} ({LATENCY_UNIT_OF_MEASURE})", "Peer Types")
print(f"Wired Latency Deviation Emulated to Physical: {deviation(median(wiredEmuEmuLatencyData), median(wiredPhyPhyLatencyData))}")
print(f"Wired Latency Deviation Emulated to Physical: {deviation(median(wiredEmuPhyLatencyData), median(wiredPhyPhyLatencyData))}")

## Plot subplots
throughputData = [wiredEmuEmuThroughputData, ciWiredEmuEmuThroughputData, wiredEmuPhyThroughputData, ciWiredEmuPhyThroughputData, wiredPhyPhyThroughputData, ciWiredPhyPhyThroughputData]
rttData = [wiredEmuEmuRttData, ciWiredEmuEmuRttData, wiredEmuPhyRttData, ciWiredEmuPhyRttData, wiredPhyPhyRttData, ciWiredPhyPhyRttData]
plotBarsSubplots(throughputData, rttData, THROUGHPUT_EXPERIMENT_NAME, WIRED, [THROUGHPUT_UNIT_OF_MEASURE, RTT_UNIT_OF_MEASURE], ["Test1", "Test2"])

throughputData = [wiredEmuEmuThroughputData, wiredEmuPhyThroughputData, wiredPhyPhyThroughputData]
rttData = [wiredEmuEmuRttData, wiredEmuPhyRttData, wiredPhyPhyRttData]
boxPlotSubplots(throughputData, rttData, [THROUGHPUT_EXPERIMENT_NAME, RTT_EXPERIMENT_NAME], [EMULATED, HYBRID, PHYSICAL], [f"{THROUGHPUT_EXPERIMENT_NAME} ({THROUGHPUT_UNIT_OF_MEASURE})", f"{RTT_EXPERIMENT_NAME} ({RTT_UNIT_OF_MEASURE})"], ["Peer Types", "Peer Types"])


# Wireless
## Throughput
minimunLength = minLen([wirelessEmuEmuThroughputData, wirelessEmuPhyThroughputData, wirelessPhyPhyThroughputData])
simplePlot(wirelessEmuEmuThroughputData[:minimunLength], wirelessEmuPhyThroughputData[:minimunLength], wirelessPhyPhyThroughputData[:minimunLength], THROUGHPUT_EXPERIMENT_NAME, WIRELESS, THROUGHPUT_UNIT_OF_MEASURE)
#plotConfidenceInterval(ciWirelessEmuEmuThroughputData, ciWirelessEmuPhyThroughputData, ciWirelessPhyPhyThroughputData, THROUGHPUT_EXPERIMENT_NAME, WIRELESS)
plotBars(wirelessEmuEmuThroughputData, ciWirelessEmuEmuThroughputData, wirelessEmuPhyThroughputData, ciWirelessEmuPhyThroughputData, wirelessPhyPhyThroughputData, ciWirelessPhyPhyThroughputData, THROUGHPUT_EXPERIMENT_NAME, WIRELESS, THROUGHPUT_UNIT_OF_MEASURE)
boxPlot([wirelessEmuEmuThroughputData, wirelessEmuPhyThroughputData, wirelessPhyPhyThroughputData], f"{WIRELESS} {THROUGHPUT_EXPERIMENT_NAME}", [EMULATED, HYBRID, PHYSICAL], f"{THROUGHPUT_EXPERIMENT_NAME} ({THROUGHPUT_UNIT_OF_MEASURE})", "Peer Types")
print(f"Wireless Throughput Deviation Emulated to Physical: {deviation(median(wirelessEmuEmuThroughputData), median(wirelessPhyPhyThroughputData))}")
print(f"Wireless Throughput Deviation Emulated to Physical: {deviation(median(wirelessEmuPhyThroughputData), median(wirelessPhyPhyThroughputData))}")

## RTT
minimunLength = minLen([wirelessEmuEmuRttData, wirelessEmuPhyRttData, wirelessPhyPhyRttData])
simplePlot(wirelessEmuEmuRttData[:minimunLength], wirelessEmuPhyRttData[:minimunLength], wirelessPhyPhyRttData[:minimunLength], RTT_EXPERIMENT_NAME, WIRELESS, RTT_UNIT_OF_MEASURE)
#plotConfidenceInterval(ciWirelessEmuEmuRttData, ciWirelessEmuPhyRttData, ciWirelessPhyPhyRttData, RTT_EXPERIMENT_NAME, WIRELESS)
plotBars(wirelessEmuEmuRttData, ciWirelessEmuEmuRttData, wirelessEmuPhyRttData, ciWirelessEmuPhyRttData, wirelessPhyPhyRttData, ciWirelessPhyPhyRttData, RTT_EXPERIMENT_NAME, WIRELESS, RTT_UNIT_OF_MEASURE)
boxPlot([wirelessEmuEmuRttData, wirelessEmuPhyRttData, wirelessPhyPhyRttData], f"{WIRELESS} {RTT_EXPERIMENT_NAME}", [EMULATED, HYBRID, PHYSICAL], f"{RTT_EXPERIMENT_NAME} ({RTT_UNIT_OF_MEASURE})", "Peer Types")
print(f"Wireless Rtt Deviation Emulated to Physical: {deviation(median(wirelessEmuEmuRttData), median(wirelessPhyPhyRttData))}")
print(f"Wireless Rtt Deviation Emulated to Physical: {deviation(median(wirelessEmuPhyRttData), median(wirelessPhyPhyRttData))}")

## Latency
minimunLength = minLen([wirelessEmuEmuLatencyData, wirelessEmuPhyLatencyData, wirelessPhyPhyLatencyData])
simplePlot(wirelessEmuEmuLatencyData[:minimunLength], wirelessEmuPhyLatencyData[:minimunLength], wirelessPhyPhyLatencyData[:minimunLength], LATENCY_EXPERIMENT_NAME, WIRELESS, LATENCY_UNIT_OF_MEASURE)
#plotConfidenceInterval(ciWirelessEmuEmuLatencyData, ciWirelessEmuPhyLatencyData, ciWirelessPhyPhyLatencyData, LATENCY_EXPERIMENT_NAME, WIRELESS)
plotBars(wirelessEmuEmuLatencyData, ciWirelessEmuEmuLatencyData, wirelessEmuPhyLatencyData, ciWirelessEmuPhyLatencyData, wirelessPhyPhyLatencyData, ciWirelessPhyPhyLatencyData, LATENCY_EXPERIMENT_NAME, WIRELESS, LATENCY_UNIT_OF_MEASURE)
boxPlot([wirelessEmuEmuLatencyData, wirelessEmuPhyLatencyData, wirelessPhyPhyLatencyData], f"{WIRELESS} {LATENCY_EXPERIMENT_NAME}", [EMULATED, HYBRID, PHYSICAL], f"{LATENCY_EXPERIMENT_NAME} ({LATENCY_UNIT_OF_MEASURE})", "Peer Types")
print(f"Wireless Latency Deviation Emulated to Physical: {deviation(median(wirelessEmuEmuLatencyData), median(wirelessPhyPhyLatencyData))}")
print(f"Latency Deviation Emulated to Physical: {deviation(median(wirelessEmuPhyLatencyData), median(wirelessPhyPhyLatencyData))}")

## Plot Subplots
throughputData = [wirelessEmuEmuThroughputData, wirelessEmuPhyThroughputData, wirelessPhyPhyThroughputData]
rttData = [wirelessEmuEmuRttData, wirelessEmuPhyRttData, wirelessPhyPhyRttData]
boxPlotSubplots(throughputData, rttData, [THROUGHPUT_EXPERIMENT_NAME, RTT_EXPERIMENT_NAME], [EMULATED, HYBRID, PHYSICAL], [f"{THROUGHPUT_EXPERIMENT_NAME} ({THROUGHPUT_UNIT_OF_MEASURE})", f"{RTT_EXPERIMENT_NAME} ({RTT_UNIT_OF_MEASURE})"], ["Peer Types", "Peer Types"])


# LFT vs Mininet Time
## Deployment Time
plotToolComparison(lftDeploymentValues, errLftDeployTime, mininetDeploymentValues, errMnDeployTime, "Deployment Time", "s")

# Undeployment Time
plotToolComparison(lftUndeploymentValues, errLftUndeployTime, mininetUndeploymentValues, errMnUndeployTime, "Tear Down Topology Time", "s")

# DeploymentMem Time
plotToolComparison(lftDeploymentMemValues, errLftDeployMem, mininetDeploymentMemValues, errMnDeployMem, "Deployment Memory Consumption", "GB")








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
plt.ylim(0, 1100)
plt.xticks(range(len(columns)), columns)
plt.ylabel("Throughput (MBps)")
plt.title('Wired Experiment Throughput')
plt.show()
#https://python-graph-gallery.com/8-add-confidence-interval-on-barplot/