from containernet.link import TCLink
from containernet.net import Containernet


class DeployMininet():
        def deploy(self, size):
                self.net = Containernet()
                s1 = self.net.addSwitch("s1")
                [self.__addHost(i, s1) for i in range(size)]
                self.net.start()
        def __addHost(self, counter, switch):
                image = "ubuntu:trusty"
                host = self.net.addDocker(f"d{counter+1}", ip=f"10.0.{int(counter/256)}.{(counter+2)%256}", dimage=image)
                self.net.addLink(host, switch)
        def undeploy(self):
                self.net.stop()

