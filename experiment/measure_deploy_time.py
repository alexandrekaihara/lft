from experiment.deploy_lft import DeployLFT
from time import time, sleep
from experiment.deploy_mininet import DeployMininet
from pandas import DataFrame
from matplotlib import pyplot as plt
from subprocess import run
from threading import Thread


def barPlot(dataframe, title):
    [plt.bar(dataframe.index, dataframe[column], label=column) for column in dataframe.columns]
    plt.title(title)
    plt.xlabel("Nodes")
    plt.legend()
    plt.show()


maxMem = 0
def measureMemory():
    maxMem = 0
    while(True):
        out = run('free | grep Mem | grep -oP \'^\D*\d+\D*\K\d+\'', shell=True, capture_output=True, text=True)
        aux = int(out.stdout)
        if aux > maxMem:
            maxMem = aux
        sleep(1)


replicas = 30
sizes = [1, 4, 16, 64, 248]
coolDownTime = 10


# Measure deployment and Undeployment time of LFT
deployLftDf = DataFrame(columns = sizes)
undeployLftDf = DataFrame(columns = sizes)
dlft = DeployLFT()
try:
    for i in range(replicas):
        lftDeployTime = []
        lftUndeployTime = []
        for size in sizes:
            start = time()
            dlft.deploy(size)
            lftDeployTime.append(time() - start)
            dlft.getReferences(size)
            sleep(coolDownTime)
            start = time()
            dlft.undeploy()
            end = time()
            lftUndeployTime.append(time() - start)
            sleep(coolDownTime)
        deployLftDf.loc[i] = lftDeployTime
        undeployLftDf.loc[i] = lftUndeployTime
except:
    dlft.getReferences(sizes[-1])
    dlft.undeploy()
deployLftDf.to_csv('results/data/deployLftTime.csv', index=False)
undeployLftDf.to_csv('results/data/undeployLftTime.csv', index=False)
#barPlot(deployLftDf, "LFT deployment time")
#barPlot(undeployLftDf, "LFT undeployment time")



# Measure Memory consumption of LFT
deployMemLftDf = DataFrame(columns = sizes)
try:
    for i in range(replicas):
        lftDeployMem = []
        for size in sizes:
            t = Thread(measureMemory)
            t.start()
            dlft.deploy(size)
            t.stop()
            lftDeployMem.append(maxMem)
            dlft.getReferences(size)
            dlft.undeploy()
            sleep(coolDownTime)
        deployMemLftDf.loc[i] = lftDeployMem
except:
    dlft.getReferences(sizes[-1])
    dlft.undeploy()
deployMemLftDf.to_csv('results/data/deployLftMem.csv', index=False)



# Measure deployment and Undeployment time of Mininet
deployMnDf = DataFrame(columns = sizes)
undeployMnDf = DataFrame(columns = sizes)
try:
    for i in range(replicas):
        mnDeployTime = []
        mnUndeployTime = []
        dmn = DeployMininet()
        for size in sizes:
            start = time()
            dmn.deploy(size)
            mnDeployTime.append(time() - start)
            sleep(coolDownTime)
            start = time()
            dmn.undeploy()
            mnUndeployTime.append(time() - start)
            sleep(coolDownTime)
        deployMnDf.loc[i] = mnDeployTime
        undeployMnDf.loc[i] = mnUndeployTime
except:
    dmn.undeploy()
deployMnDf.to_csv('results/data/deployMnTime.csv', index=False)
undeployMnDf.to_csv('results/data/undeployMnTime.csv', index=False)
#barPlot(deployMnDf, "ContainerNet deployment time")
#barPlot(undeployLftDf, "ContainerNet undeployment time")



# Measure deployment memory of Mininet
deployMemMnDf = DataFrame(columns = sizes)
try:
    for i in range(replicas):
        mnDeployMem = []
        dmn = DeployMininet()
        for size in sizes:
            t = Thread(measureMemory)
            t.start()
            dmn.deploy(size)
            t.stop()
            lftDeployMem.append(maxMem)
            dmn.undeploy()
            sleep(coolDownTime)
        deployMnDf.loc[i] = mnDeployMem
except:
    dmn.undeploy()
deployMemMnDf.to_csv('results/data/deployMnTime.csv', index=False)
