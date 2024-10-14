from time import time, sleep
from experiment.deploy_mininet import DeployMininet


dmn = DeployMininet()
nodes = 100
deployTime = {}
undeployTime = {}


for i in range(100):
	start = time()
	dmn.deploy(i)
	deployTime[i] = time() - start
	sleep(3)
	start = time()
	dmn.undeploy()
	undeployTime[i] = time() - start
	sleep(3)


print(deployTime)
print(undeployTime)
