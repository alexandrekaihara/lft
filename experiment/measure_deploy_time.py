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


replicas = 60
sizes = [1, 4, 16, 64, 248]
coolDownTime = 20

# Measure deployment and Undeployment time of LFT
deployLftDf = DataFrame(columns = sizes)
undeployLftDf = DataFrame(columns = sizes)
dlft = DeployLFT()
try:
    for i in range(replicas):
        print(f'LFT Deployment and Undeployment Assessment: Replica {i+1}')
        lftDeployTime = []
        lftUndeployTime = []
        for size in sizes:
            print(f'Deploying {size} node(s)')
            start = time()
            dlft.deploy(size)
            lftDeployTime.append(time() - start)
            print(f'LFT Deployment Time: {lftDeployTime[-1]}')
            dlft.getReferences(size)
            sleep(coolDownTime)
            start = time()
            dlft.undeploy()
            end = time()
            lftUndeployTime.append(time() - start)
            print(f'LFT Undeployment Time: {lftUndeployTime[-1]}')
            sleep(coolDownTime)
        print(f'LFT Deployment times for replica {i+1} were {lftDeployTime}')
        print(f'LFT Undeployment times for replica {i+1} were {lftUndeployTime}')
        deployLftDf.loc[i] = lftDeployTime
        undeployLftDf.loc[i] = lftUndeployTime
except Exception as ex:
    print(f"Caught an exception. {ex}")
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
        print(f'LFT Memory Consumption Assessment: Replica {i+1}')
        lftDeployMem = []
        for size in sizes:
            print(f'Deploying {size} node(s)')
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
        print(f'LFT Deployment Memory Consumption for replica {i+1} were {lftDeployMem}')
        deployMemLftDf.loc[i] = lftDeployMem
except Exception as ex:
    print(f"Caught an exception. {ex}")
    dlft.getReferences(sizes[-1])
    dlft.undeploy()


deployMemLftDf.to_csv(f'{RESULTS_PATH}deployLftMem.csv', index=False)



# Measure deployment and Undeployment time of Mininet
deployMnDf = DataFrame(columns = sizes)
undeployMnDf = DataFrame(columns = sizes)
try:
    for i in range(replicas):
        print(f'Mininet-WiFi Deployment and Undeployment Assessment: Replica {i+1}')
        mnDeployTime = []
        mnUndeployTime = []
        dmn = DeployMininet()
        for size in sizes:
            print(f'Deploying {size} node(s)')
            start = time()
            dmn.deploy(size)
            mnDeployTime.append(time() - start)
            print(f'Mininet-WiFi Deployment Time: {mnDeployTime[-1]}')
            sleep(coolDownTime)
            start = time()
            dmn.undeploy()
            mnUndeployTime.append(time() - start)
            print(f'Mininet-WiFi Undeployment Time: {mnUndeployTime[-1]}')
            sleep(coolDownTime)
        print(f'Mininet Containernet Deployment times for replica {i+1} were {mnDeployTime}')
        print(f'Mininet Containernet Undeployment times for replica {i+1} were {mnUndeployTime}')
        deployMnDf.loc[i] = mnDeployTime
        undeployMnDf.loc[i] = mnUndeployTime
except Exception as ex:
    print(f"Caught an exception. {ex}")
    dmn.undeploy()


deployMnDf.to_csv(f'{RESULTS_PATH}deployMnTime.csv', index=False)
undeployMnDf.to_csv(f'{RESULTS_PATH}undeployMnTime.csv', index=False)
#barPlot(deployMnDf, "ContainerNet deployment time")
#barPlot(undeployLftDf, "ContainerNet undeployment time")



# Measure deployment memory of Mininet
deployMemMnDf = DataFrame(columns = sizes)
try:
    for i in range(replicas):
        print(f'Mininet-Wifi Memory Consumption Assessment: Replica {i+1}')
        mnDeployMem = []
        dmn = DeployMininet()
        for size in sizes:
            print(f'Deploying {size} node(s)')
            t = Thread(measureMemory)
            t.start()
            dmn.deploy(size)
            continueThread = False
            t.join()
            lftDeployMem.append(maxMem)
            print(f'Mininet-WiFi Deployment Max Memory Consumption: {mnDeployMem}')
            dmn.undeploy()
            sleep(coolDownTime)
        print(f'Mininet-WiFi Deployment Memory Consumption for replica {i+1} were {mnDeployMem}')
        deployMnDf.loc[i] = mnDeployMem
except Exception as ex:
    print(f"Caught an exception. {ex}")
    dmn.undeploy()


deployMemMnDf.to_csv(f'{RESULTS_PATH}deployMnTime.csv', index=False)
