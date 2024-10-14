from experiment.deploy_lft import DeployLFT
from time import time, sleep
from experiment.deploy_mininet import DeployMininet
from pandas import DataFrame, read_csv, concat
from matplotlib import pyplot as plt
from subprocess import run
from threading import Thread
from os.path import isfile
from experiment.constants import *


def barPlot(dataframe, title):
    [plt.bar(dataframe.index, dataframe[column], label=column) for column in dataframe.columns]
    plt.title(title)
    plt.xlabel("Nodes")
    plt.legend()
    plt.show()


def cleanupContainers():
    out = run('docker ps -qa', shell=True, capture_output=True)
    containerIds = out.stdout.decode().split()
    [run(f'docker rm -f {id}', shell=True) for id in containerIds]


def saveFile(dataframe, filename):
    if isfile(filename):
        dataframe = concat([dataframe, read_csv(filename)], axis=0)
    dataframe.to_csv(filename, index=False)


awaitStabilizeMemoryTime = 5
maxMem = 0
continueThread = True
result = 0
def measureMemory(startMemoryUsage):
    global result, maxMem, continueThread
    maxMem = startMemoryUsage
    while(continueThread):
        aux = getCurrentMemoryUsage()
        if aux > maxMem:
            maxMem = aux
            result = maxMem - startMemoryUsage
        sleep(1)


def getCurrentMemoryUsage():
    command = 'free | grep Mem | grep -oP \'^\D*\d+\D*\K\d+\''
    out = run(command, shell=True, capture_output=True, text=True)
    return int(out.stdout)


replicas = 30
sizes = [1, 4, 16, 64, 256]
coolDownTime = 20
cleanupContainers()


# Measure deployment and Undeployment time of LFT
deployLftDf = DataFrame(columns = sizes)
undeployLftDf = DataFrame(columns = sizes)
dlft = DeployLFT()
for i in range(replicas):
    print(f'LFT Deployment and Undeployment Assessment: Replica {i+1}')
    lftDeployTime = []
    lftUndeployTime = []
    for size in sizes:
        try:
            print(f'Deploying {size} node(s)')
            start = time()
            dlft.deploy(size)
            lftDeployTime.append(time() - start)
            print(f'LFT Deployment Time: {lftDeployTime}')
            dlft.getReferences(size)
            sleep(coolDownTime)
            start = time()
            dlft.undeploy()
            end = time()
            lftUndeployTime.append(time() - start)
            print(f'LFT Undeployment Time: {lftUndeployTime}')
            sleep(coolDownTime)
        except Exception as ex:
            print(f"Caught an exception. {ex}")
            dlft.getReferences(sizes)
            cleanupContainers()
            continue
    print(f'LFT Deployment times for replica {i+1} were {lftDeployTime}')
    print(f'LFT Undeployment times for replica {i+1} were {lftUndeployTime}')
    deployLftDf.loc[i] = lftDeployTime
    undeployLftDf.loc[i] = lftUndeployTime


cleanupContainers()
saveFile(deployLftDf, f'{RESULTS_PATH}deployLftTime.csv')
saveFile(undeployLftDf, f'{RESULTS_PATH}undeployLftTime.csv')
#barPlot(deployLftDf, "LFT deployment time")
#barPlot(undeployLftDf, "LFT undeployment time")



# Measure Memory consumption of LFT
awaitStabilizeMemoryTime = 5

deployMemLftDf = DataFrame(columns = sizes)
for i in range(replicas):
    print(f'LFT Memory Consumption Assessment: Replica {i+1}')
    lftDeployMem = []
    for size in sizes:
        try:
            print(f'Deploying {size} node(s)')
            maxMem = 0
            continueThread = True
            startMemoryUsage = getCurrentMemoryUsage()
            t = Thread(target=measureMemory, args=(startMemoryUsage,))
            t.start()
            sleep(awaitStabilizeMemoryTime)
            dlft.deploy(size)
            sleep(awaitStabilizeMemoryTime)
            continueThread = False
            t.join()
            lftDeployMem.append(result)
            print(f'LFT Deployment Max Memory Consumption: {lftDeployMem}')
            dlft.getReferences(size)
            dlft.undeploy()
            sleep(coolDownTime)
        except Exception as ex:
            print(f"Caught an exception. {ex}")
            dlft.getReferences(sizes)
            cleanupContainers()
            continue
    print(f'LFT Deployment Memory Consumption for replica {i+1} were {lftDeployMem}')
    deployMemLftDf.loc[i] = lftDeployMem


cleanupContainers()
saveFile(deployMemLftDf, f'{RESULTS_PATH}deployLftMem.csv')



# Measure deployment and Undeployment time of Mininet
deployMnDf = DataFrame(columns = sizes)
undeployMnDf = DataFrame(columns = sizes)
for i in range(replicas):
    print(f'Mininet-WiFi Deployment and Undeployment Assessment: Replica {i+1}')
    mnDeployTime = []
    mnUndeployTime = []
    dmn = DeployMininet()
    for size in sizes:
        try:
            print(f'Deploying {size} node(s)')
            start = time()
            dmn.deploy(size)
            mnDeployTime.append(time() - start)
            print(f'Mininet-WiFi Deployment Time: {mnDeployTime}')
            sleep(coolDownTime)
            start = time()
            dmn.undeploy()
            mnUndeployTime.append(time() - start)
            print(f'Mininet-WiFi Undeployment Time: {mnUndeployTime}')
            sleep(coolDownTime)
        except Exception as ex:
            print(f"Caught an exception. {ex}")
            cleanupContainers()
            continue
    print(f'Mininet Containernet Deployment times for replica {i+1} were {mnDeployTime}')
    print(f'Mininet Containernet Undeployment times for replica {i+1} were {mnUndeployTime}')
    deployMnDf.loc[i] = mnDeployTime
    undeployMnDf.loc[i] = mnUndeployTime


cleanupContainers()
saveFile(deployMnDf, f'{RESULTS_PATH}deployMnTime.csv')
saveFile(undeployMnDf, f'{RESULTS_PATH}undeployMnTime.csv')
#barPlot(deployMnDf, "ContainerNet deployment time")
#barPlot(undeployLftDf, "ContainerNet undeployment time")



# Measure deployment memory of Mininet
deployMemMnDf = DataFrame(columns = sizes)
for i in range(replicas):
    print(f'Mininet-Wifi Memory Consumption Assessment: Replica {i+1}')
    mnDeployMem = []
    dmn = DeployMininet()
    for size in sizes:
        try:
            print(f'Deploying {size} node(s)')
            maxMem = 0
            result = 0
            continueThread = True
            startMemoryUsage = getCurrentMemoryUsage()
            t = Thread(target=measureMemory, args=(startMemoryUsage,))
            t.start()
            sleep(awaitStabilizeMemoryTime)
            dmn.deploy(size)
            sleep(awaitStabilizeMemoryTime)
            continueThread = False
            t.join()
            mnDeployMem.append(result)
            print(f'Mininet-WiFi Deployment Max Memory Consumption: {mnDeployMem}')
            dmn.undeploy()
            sleep(coolDownTime)
        except Exception as ex:
            print(f"Caught an exception. {ex}")
            cleanupContainers()
            continue
    print(f'Mininet-WiFi Deployment Memory Consumption for replica {i+1} were {mnDeployMem}')
    deployMemMnDf.loc[i] = mnDeployMem


cleanupContainers()
saveFile(deployMemMnDf, f'{RESULTS_PATH}deployMnMem.csv')
