from experiment.deploy_lft import DeployLFT
from time import time, sleep
from time import time, sleep
from experiment.deploy_mininet import DeployMininet
from pandas import DataFrame
from matplotlib import pyplot as plt


def barPlot(dataframe, title):
    [plt.bar(dataframe.index, dataframe[column], label=column) for column in dataframe.columns]
    plt.title(title)
    plt.xlabel("Nodes")
    plt.legend()
    plt.show()


replicas = 30
sizes = [1, 4, 16, 64, 248]
coolDownTime = 10

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
barPlot(deployLftDf, "LFT deployment time")
barPlot(undeployLftDf, "LFT undeployment time")


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
barPlot(deployMnDf, "ContainerNet deployment time")
barPlot(undeployLftDf, "ContainerNet undeployment time")


