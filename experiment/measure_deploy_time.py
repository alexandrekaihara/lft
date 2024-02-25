from experiment.deploy_lft import DeployLFT
from time import time, sleep
from experiment.deploy_mininet import DeployMininet
from pandas import DataFrame
from matplotlib import pyplot as plt
from subprocess import run
from threading import Thread
from experiment.constants import *


def barPlot(dataframe, title):
    [plt.bar(dataframe.index, dataframe[column], label=column) for column in dataframe.columns]
    plt.title(title)
    plt.xlabel("Nodes")
    plt.legend()
    plt.show()


maxMem = 0
continueThread = True
def measureMemory():
    maxMem = 0
    continueThread = True
    while(continueThread):
        out = run('free | grep Mem | grep -oP \'^\D*\d+\D*\K\d+\'', shell=True, capture_output=True, text=True)
        aux = int(out.stdout)
        if aux > maxMem:
            maxMem = aux
        sleep(1)


replicas = 1
sizes = [1, 4, 16, 64, 248]
coolDownTime = 20

# Measure deployment and Undeployment time of LFT
deployLftDf = DataFrame(columns = sizes)
undeployLftDf = DataFrame(columns = sizes)
dlft = DeployLFT()
try:
    for i in range(replicas):
        print(f'LFT Deployment and Undeployment Assessment: Replica {i}')
        lftDeployTime = []
        lftUndeployTime = []
        for size in sizes:
            print(f'Deploying {size} nodes')
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
        deployLftDf.loc[i] = lftDeployTime
        undeployLftDf.loc[i] = lftUndeployTime
except:
    dlft.getReferences(sizes[-1])
    dlft.undeploy()


deployLftDf.to_csv(f'{RESULTS_PATH}deployLftTime.csv', index=False)
undeployLftDf.to_csv(f'{RESULTS_PATH}undeployLftTime.csv', index=False)
#barPlot(deployLftDf, "LFT deployment time")
#barPlot(undeployLftDf, "LFT undeployment time")



# Measure Memory consumption of LFT
deployMemLftDf = DataFrame(columns = sizes)
try:
    for i in range(replicas):
        print(f'LFT Memory Consumption Assessment: Replica {i}')
        lftDeployMem = []
        for size in sizes:
            print(f'Deploying {size} nodes')
            t = Thread(measureMemory)
            t.start()
            dlft.deploy(size)
            continueThread = False
            t.join()
            print(f'LFT Deployment Max Memory Consumption: {lftDeployMem}')
            lftDeployMem.append(maxMem)
            dlft.getReferences(size)
            dlft.undeploy()
            sleep(coolDownTime)
        deployMemLftDf.loc[i] = lftDeployMem
except:
    dlft.getReferences(sizes[-1])
    dlft.undeploy()


deployMemLftDf.to_csv(f'{RESULTS_PATH}deployLftMem.csv', index=False)



# Measure deployment and Undeployment time of Mininet
deployMnDf = DataFrame(columns = sizes)
undeployMnDf = DataFrame(columns = sizes)
try:
    for i in range(replicas):
        print(f'Mininet-WiFi Deployment and Undeployment Assessment: Replica {i}')
        mnDeployTime = []
        mnUndeployTime = []
        dmn = DeployMininet()
        for size in sizes:
            print(f'Deploying {size} nodes')
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
        deployMnDf.loc[i] = mnDeployTime
        undeployMnDf.loc[i] = mnUndeployTime
except:
    dmn.undeploy()


deployMnDf.to_csv(f'{RESULTS_PATH}deployMnTime.csv', index=False)
undeployMnDf.to_csv(f'{RESULTS_PATH}undeployMnTime.csv', index=False)
#barPlot(deployMnDf, "ContainerNet deployment time")
#barPlot(undeployLftDf, "ContainerNet undeployment time")



# Measure deployment memory of Mininet
deployMemMnDf = DataFrame(columns = sizes)
try:
    for i in range(replicas):
        print(f'Mininet-Wifi Memory Consumption Assessment: Replica {i}')
        mnDeployMem = []
        dmn = DeployMininet()
        for size in sizes:
            print(f'Deploying {size} nodes')
            t = Thread(measureMemory)
            t.start()
            dmn.deploy(size)
            continueThread = False
            t.join()
            lftDeployMem.append(maxMem)
            print(f'Mininet-WiFi Deployment Max Memory Consumption: {lftDeployMem}')
            dmn.undeploy()
            sleep(coolDownTime)
        deployMnDf.loc[i] = mnDeployMem
except:
    dmn.undeploy()

    
deployMemMnDf.to_csv(f'{RESULTS_PATH}deployMnTime.csv', index=False)
