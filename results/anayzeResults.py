import matplotlib.pyplot as plt
from results.preprocess_throughput import Throughput
from scipy import stats
import numpy as np
from json import load
from glob import glob


def confidence_interval(data, confidence=0.95):
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
    

wiredEmuEmuThroughputData = loadThroughputData("results/data/wired_emu_emu_throughput_*.json")
wiredEmuPhyThroughputData = loadThroughputData("results/data/wired_emu_emu_throughput_*.json")
wiredPhyPhyThroughputData = loadThroughputData("results/data/wired_emu_emu_throughput_*.json")

wirelessEmuEmuThroughputPaths = loadThroughputData("results/data/wireless_emu_emu_throughput_*.json")


#plt.plot(wiredThroughputData, label='Wired')
plt.plot(wirelessThroughputData, label='Wireless')
plt.title('Throughput Data')
plt.xlabel('Time')
plt.ylabel('Throughput')
plt.show()


c1 = confidence_interval(wiredThroughputData)
c2 = confidence_interval(wirelessThroughputData)

plt.plot(c1, (0, 0),'ro-',color='orange')
plt.plot(c2, (1, 1),'ro-',color='orange')

plt.xlabel('Confidence Intervals')
plt.ylabel('Mean')
plt.title('Three Confidence Intervals')

plt.yticks(range(len(3)), ['CI Wired', 'CI Wireless'])

plt.show()
