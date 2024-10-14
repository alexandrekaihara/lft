from profissa_lft.host import Host
from profissa_lft.switch import Switch


class DeployLFT():
	def deploy(self, size):
		s1 = Switch("s1")
		s1.instantiate()
		[self.__addHost(i, s1) for i in range(size)]

	def __addHost(self, counter, switch):
		host = Host(f"h{counter}")
		host.instantiate(dockerImage="ubuntu:trusty", runCommand="tail -f /dev/null")
		switch.connect(host, f"s1h{counter}", f"h{counter}s1")
		host.setIp(f"10.0.{int(counter/256)}.{(counter+2)%256}", 24, f"h{counter}s1")

	def getReferences(self, size):
		self.nodes = []
		self.nodes.append(Switch("s1"))
		[self.nodes.append(Host(f"h{i}")) for i in range(size)]

	def undeploy(self):
		[node.delete() for node in self.nodes]
