import os
import random
import subprocess
import time
from pathlib import Path

from . import utils
from ..router_quagga import Router
from .constants import DEFAULT_CONFIG, RANDOM_RANGES
from .dash_client import DashClient
from .dash_server import DashServer
from ..onos import ONOS
from ..switch_modified import Switch
from onos_topologies.iperf_experiment.iperf_client import IperfClient
from onos_topologies.iperf_experiment.iperf_server import IperfServer


class DashTopology:
    """
    Encapsulates all logic to build, configure and test the topology.
    """

    def __init__(self, 
                 config: dict = DEFAULT_CONFIG, 
                 results_dir: Path = None,
                 iperf: bool = False,
                 onos_version: str = "onosproject/onos:2.5.0"
                 ):
        self.config = config

        # Default version v2.5 for compatibility with measuring tools
        self.onos_version = onos_version

        (self.switch_ip_range,
         self.server_ip_range, 
         self.client_ip_range, 
         self.server_pop_names) = self.__get_ip_ranges(self.config["pops"])
        
        # Only created for the iperf experiment. If true, clients and servers use iperf instead of the typical dash algo
        self.iperf = iperf  

        # Map: {pop_name: switch_name}
        self.pop_to_sname = {pop[0]: f"s{i}" for i, pop in enumerate(self.config['pops'])}

        # Map: {client_name: client_obj}
        self.clients = {}   

        # Map: {server_name: server_obj}
        self.servers = {}

        # Map: {pop_name: switch_obj}
        self.switches = {}

        # Map: {pop_name: router_obj} (only for OSPF!!)
        self.routers = {}

        # ONOS controller (object)
        self.controller = ""

        # PoP list of client Node (used by collectFlows to select host-facing ports)
        self.hosts_by_pop = {pop[0]: [] for pop in self.config['pops']}

        # Host-side directory that will be bind-mounted into each switch at /results/dash
        self.host_results = Path(results_dir).resolve() if results_dir else None

        self.onos_ip = ""

    # Brief: used to know the servers and clients IP range and switches linked to servers
    def __get_ip_ranges(self, pops: tuple, ip_prefix: str = "192.168.0.") -> tuple:
        server_ip_range = []
        client_ip_range = []
        
        
        if "1.5" in self.onos_version:
            # L3 (1.5): Unique /24 subnet per PoP to avoid ARP conflicts in routed environments
            for i, (pop, num_clients, num_servers) in enumerate(pops):
                subnet_prefix = f"192.168.{10 + i}" 
                for s in range(num_servers):
                    server_ip_range.append(f"{subnet_prefix}.{s + 10}")
                for c in range(num_clients):
                    client_ip_range.append(f"{subnet_prefix}.{c + 100}")
        else:
            # L2 (2.5.0): Flat 192.168.0.0/24 network for all PoPs
            tot_servers = sum(p[2] for p in pops)
            tot_clients = sum(p[1] for p in pops)
            server_ip_range = [f"192.168.0.{i+1}" for i in range(tot_servers)]
            client_ip_range = [f"192.168.0.{i + tot_servers + 1}" for i in range(tot_clients)]

        # Inter-router /30 links remain the same for measuring RTT or OSPF adjacencies
        max_links = len(pops) * (len(pops) - 1) // 2
        switch_ip_range = [f"10.0.0.{i+1}" for i in range(max_links * 2)]
        
        return (switch_ip_range, server_ip_range, client_ip_range, [p[0] for p in pops])


    # Brief: Create and configure all DashServer containers
    def __create_servers(self, iperf=False):
        ds_index = 0
        print(f"[Experiment] ... Creating DASH servers")
        
        # Get list of PoP names to calculate subnet indices
        pop_names = [p[0] for p in self.config["pops"]]
        for pop, _, num_servers in self.config["pops"]:
            pop_idx = pop_names.index(pop)
            
            # Select edge node and define gateway based on network mode
            if "1.5" in self.onos_version:
                edge_node = self.routers[pop]
                gateway_ip = f"192.168.{10 + pop_idx}.1" # each PoP gets a unique /24 subnet
            else:
                edge_node = self.switches[pop]
                gateway_ip = None

            for _ in range(num_servers):
                throughput = delay = jitter = "-" 
                dsname = f"ds{ds_index}"
                ds_if, sw_if = f"{dsname}{self.pop_to_sname[pop]}", f"{self.pop_to_sname[pop]}{dsname}"

                ds = IperfServer(dsname) if iperf else DashServer(dsname)
                ds.instantiate(mapPorts=False)
                ds.connect(edge_node, ds_if, sw_if)

                server_ip = self.server_ip_range[ds_index]
                ds.setIp(server_ip, 24, ds_if)
                print(f"  ... Host {dsname} ({server_ip}) created and linked to {pop}")

                # Configure L3 Routing and OSPF advertising
                if gateway_ip:
                    edge_node.setIp(gateway_ip, 24, sw_if)
                    ds.run(f"ip route add default via {gateway_ip}")
                    
                    # Inject configuration into Quagga daemons
                    edge_node.run(f"echo -e 'interface {sw_if}\\n ip address {gateway_ip}/24\\n!' >> /etc/quagga/zebra.conf")
                    edge_node.run(f"echo -e 'router ospf\\n network 192.168.{10 + pop_idx}.0/24 area 0.0.0.0\\n!' >> /etc/quagga/ospfd.conf")
                    edge_node.run(f"echo -e 'interface {sw_if}\\n ip ospf network point-to-point\\n!' >> /etc/quagga/ospfd.conf")

                if self.config.get("apply_link_properties"):
                    if self.config.get("randomize_link_properties"):
                        throughput, delay, jitter = f"{random.choice(RANDOM_RANGES['throughput'])}mbit", f"{random.choice(RANDOM_RANGES['delay'])}ms", f"{random.choice(RANDOM_RANGES['jitter'])}ms"
                    else:
                        throughput, delay, jitter = self.config["throughput"], self.config["delay"], self.config["jitter"]

                    edge_node.setInterfaceProperties(interfaceName=sw_if, throughput=throughput, delay=delay, jitter=jitter)
                    ds.setInterfaceProperties(interfaceName=ds_if, throughput=throughput, delay=delay, jitter=jitter)
                    print(f"Throughput={throughput}, Delay={delay}, Jitter={jitter}")
                
                self.servers[dsname] = ds
                self.hosts_by_pop[pop].append(ds)
                ds_index += 1

        # Apply Quagga configurations by restarting daemons in L3 mode
        if "1.5" in self.onos_version:
             for router in self.routers.values():
                 router.run("killall -9 zebra ospfd 2>/dev/null || true && /usr/sbin/zebra -d && /usr/sbin/ospfd -d")

        print("[OK] DASH servers created!\n")


    # Brief: Create and configure all DashClient containers
    def __create_clients(self, iperf=False):
        cli_index = 0
        print(f"[Experiment] ... Creating DASH clients")
        pop_names = [p[0] for p in self.config["pops"]]

        for pop, num_clients, _ in self.config["pops"]:
            pop_idx = pop_names.index(pop)
            
            if "1.5" in self.onos_version:
                edge_node = self.routers[pop]
                gateway_ip = f"192.168.{10 + pop_idx}.1"
            else:
                edge_node = self.switches[pop]
                gateway_ip = None

            for _ in range(num_clients):
                throughput = delay = jitter = "-" 
                cname = f"cl{cli_index}"
                cl_if, sw_if = f"{cname}{self.pop_to_sname[pop]}", f"{self.pop_to_sname[pop]}{cname}"

                cl = IperfClient(cname) if iperf else DashClient(cname)
                cl.instantiate()
                cl.connect(edge_node, cl_if, sw_if)

                client_ip = self.client_ip_range[cli_index]
                cl.setIp(client_ip, 24, cl_if)
                print(f"  ... Host {cname} ({client_ip}) created and linked to {pop}")

                if gateway_ip:
                    edge_node.setIp(gateway_ip, 24, sw_if)
                    cl.run(f"ip route add default via {gateway_ip}")
                    
                    edge_node.run(f"echo -e 'interface {sw_if}\\n ip address {gateway_ip}/24\\n!' >> /etc/quagga/zebra.conf")
                    edge_node.run(f"echo -e 'router ospf\\n network 192.168.{10 + pop_idx}.0/24 area 0.0.0.0\\n!' >> /etc/quagga/ospfd.conf")
                    edge_node.run(f"echo -e 'interface {sw_if}\\n ip ospf network point-to-point\\n!' >> /etc/quagga/ospfd.conf")

                if self.config.get("apply_link_properties"):
                    if self.config.get("randomize_link_properties"):
                        throughput, delay, jitter = f"{random.choice(RANDOM_RANGES['throughput'])}mbit", f"{random.choice(RANDOM_RANGES['delay'])}ms", f"{random.choice(RANDOM_RANGES['jitter'])}ms"
                    else:
                        throughput, delay, jitter = self.config["throughput"], self.config["delay"], self.config["jitter"]

                    edge_node.setInterfaceProperties(interfaceName=sw_if, throughput=throughput, delay=delay, jitter=jitter)
                    cl.setInterfaceProperties(interfaceName=cl_if, throughput=throughput, delay=delay, jitter=jitter)
                    print(f"Throughput={throughput}, Delay={delay}, Jitter={jitter}")
                
                self.clients[cname] = cl
                self.hosts_by_pop[pop].append(cl)
                cli_index += 1
                
        # Apply Quagga configurations by restarting daemons in L3 mode
        if "1.5" in self.onos_version:
             for router in self.routers.values():
                 router.run("killall -9 zebra ospfd 2>/dev/null || true && /usr/sbin/zebra -d && /usr/sbin/ospfd -d")
                     
        print("[OK] DASH clients created!\n")


    # Brief: Create the ONOS controller, start it and activate required apps
    def __create_controller(self):
        print("\n[Experiment] ... Creating ONOS controller")
        c1 = ONOS("c1")
        dockerImage=self.onos_version
        c1.instantiate(dockerImage=dockerImage, mapPorts=True) 
        self.onos_ip = utils.get_container_ip("c1")
        c1.setCliIp(self.onos_ip) # needed in runOnosCliCommands() from Onos class
        print(f"[CTRL] ONOS IP: {self.onos_ip}")
        print("Waiting for ONOS to initialize (30s) ...")
        utils.sleep_countdown(30)

        print("[CTRL] Activating OpenFlow + Proxy Arp + Reactive Forwarding")
        apps_to_activate = ["org.onosproject.openflow", "org.onosproject.fwd", "org.onosproject.proxyarp"]
        for app in apps_to_activate:
            c1.activateONOSApps(server_ip=self.onos_ip, command=f'app activate {app}')

        container_name = "c1"
        current_dir = os.path.dirname(os.path.abspath(__file__))

        # install and activate telemetry app
        if (dockerImage == "onosproject/onos:2.5.0"):
            current_dir = os.path.dirname(os.path.abspath(__file__))
            oar_path = os.path.abspath(os.path.join(current_dir, "..", "onos_apps", "onos-apps-ONOS_Link_Quality_Measurement-oar.oar"))
            print("[CTRL] Preparing official container for the experiment...")
            
            subprocess.run(f"docker exec -u 0 {container_name} mkdir -p /home/onos", shell=True)
            subprocess.run(f"docker cp {oar_path} {container_name}:/home/onos/lft_app.oar", shell=True)
            link_cmd = "ln -snf /root/onos/apache-karaf-4.2.14 /home/onos/apache-karaf-4.2.14"
            subprocess.run(f"docker exec -u 0 {container_name} {link_cmd}", shell=True)
            
            print("[CTRL] Activating the Latency App via REST...")
            activation_cmd = (
                f'docker exec {container_name} curl -u onos:rocks -X POST '
                '-H "Content-Type:application/octet-stream" '
                '"http://localhost:8181/onos/v1/applications?activate=true" '
                '--data-binary "@/home/onos/lft_app.oar"'
            )
            subprocess.run(activation_cmd, shell=True)

        if (dockerImage == "onosproject/onos:1.5"):
            print("[CTRL] Injecting OSPF 1.6.0 via Host-side REST API...")
            ospf_oar_path = os.path.abspath(os.path.join(current_dir, "..", "onos_apps", "onos-ospf-app-1.6.0.oar"))

            if os.path.exists(ospf_oar_path):
                activation_cmd = (
                    f'curl -u onos:rocks -X POST '
                    f'-H "Content-Type:application/octet-stream" '
                    f'"http://{self.onos_ip}:8181/onos/v1/applications?activate=true" '
                    f'--data-binary "@{ospf_oar_path}"'
                )
                subprocess.run(activation_cmd, shell=True)
                print("[OK] OSPF App successfully injected!")

                # Inject OSPF configuraton json via host
                config_path = os.path.abspath(os.path.join(current_dir, "..", "onos_apps", "ospf-config.json"))
                if os.path.exists(config_path):
                    config_cmd = (
                        f'curl -u onos:rocks -X POST '
                        f'-H "Content-Type:application/json" '
                        f'"http://{self.onos_ip}:8181/onos/v1/network/configuration/" '
                        f'-d "@{config_path}"'
                    )
                    subprocess.run(config_cmd, shell=True)
                    print("[OK] OSPF Network Configuration applied!")
            else:
                print(f"[ERROR] OAR file was not found in: {ospf_oar_path}")
            
        print("[OK] ONOS is ready!\n")
        self.controller = c1 # stores c1 obj to access a few methods outside of this function


    # Brief: Create all OVS switches and connect them to the ONOS controller
    def __create_switches(self):
        if self.host_results is None:
            self.host_results = Path(os.getenv("LFT_RESULTS", "/lft/results/dash")).resolve()
            self.host_results.mkdir(parents=True, exist_ok=True)

        print(f"[Experiment] ... Creating {len(self.config['pops'])} OVS switches")
        dpid_counter = 1
        for pop, sname in self.pop_to_sname.items():
            # If pop is "PoP-BA", uf becomes "BA"
            uf = str(pop).split("-")[-1].upper()

            datapath_id = f"{dpid_counter:016x}" # ex: "0000000000000001"
            dpid_counter += 1

            sw = Switch(sname, hostPath=str(self.host_results), containerPath="/results/dash")
            sw.instantiate(
                image="alexandremitsurukaihara/lst2.0:openvswitch",
                networkMode="bridge",
                datapath_id=datapath_id,
                sw_desc=uf,
            )

            self.switches[pop] = sw
            print(f"  ... Switch {pop} as {sname} was created! dpid={datapath_id} desc={uf}")
            time.sleep(0.4)

        print(f"[CTRL] Pointing all switches to ONOS ({self.onos_ip}:6653)")
        for pop, *_ in self.config['pops']:
            self.switches[pop].setController(self.onos_ip, 6653)
        print("[OK] Controllers configured!\n")


    # Brief: Create all Quagga Routers proper for OSPF (ONOS v1.5)
    def __create_routers(self):
        print(f"[Experiment] ... Creating {len(self.config['pops'])} Quagga Routers")
        first_pop = self.config['pops'][0][0] 
        
        for pop, sname in self.pop_to_sname.items():
            n_mode = "bridge" if pop == first_pop else "none"
            node = Router(sname, hostPath=str(self.host_results), containerPath="/results/dash")
            node.instantiate(image="quagga", networkMode=n_mode)
            self.routers[pop] = node
            print(f"  ... Router {pop} as {sname} was created! (Quagga in {n_mode})")
            time.sleep(0.4)


    # Brief: Create PoP links based on self.config['adjacency_matrix']
    def __connect_switches(self):
        print("[Experiment] ... Connecting PoP-to-PoP switches")
        sw_index = 0
        connections_made = set()
        throughput = delay = jitter = "-" # defaults for printing

        for i, pop_i in enumerate(self.config['pops']):
            pop_i_name = pop_i[0] # ex: pop_i_name = "PoP-AC"; pop_i = ("PoP-AC", 0, 1)
            for j, pop_j in enumerate(self.config['pops']):
                pop_j_name = pop_j[0] # ex: pop_j_name = "PoP-CE"; pop_j = ("PoP-CE", 5, 0)
                if i == j:
                    continue
                if self.config['adjacency_matrix'][i][j] != 1:
                    continue

                edge = tuple(sorted((pop_i_name, pop_j_name)))
                if edge in connections_made:
                    continue
                connections_made.add(edge)

                si = self.pop_to_sname[pop_i_name]
                sj = self.pop_to_sname[pop_j_name]
                self.switches[pop_i_name].connect(self.switches[pop_j_name], f"{si}{sj}", f"{sj}{si}")

                if self.config.get("apply_link_properties"):
                    if self.config.get("randomize_link_properties"):
                        throughput = f"{random.choice(RANDOM_RANGES['throughput'])}mbit"
                        delay = f"{random.choice(RANDOM_RANGES['delay'])}ms"
                        jitter = f"{random.choice(RANDOM_RANGES['jitter'])}ms"
                    else:
                        throughput = self.config["throughput"]
                        delay = self.config["delay"]
                        jitter = self.config["jitter"]

                    si_obj = self.switches[pop_i_name]
                    sj_obj = self.switches[pop_j_name]
                    si_obj.setInterfaceProperties(interfaceName=f"{si}{sj}", throughput=throughput, delay=delay, jitter=jitter)
                    sj_obj.setInterfaceProperties(interfaceName=f"{sj}{si}", throughput=throughput, delay=delay, jitter=jitter)
                    print(f"Throughput={throughput}, Delay={delay}, Jitter={jitter}")

                print(f"  [LINK] {pop_i_name} <-> {pop_j_name}")
                time.sleep(0.4)

        print(f"[OK] {len(connections_made)} inter-PoP links created!\n")


    # Brief: Create PoP links for L3 Routers, assign /30 IPs and configure OSPF
    def __connect_routers(self):
        print("[Experiment] ... Connecting Quagga Routers (OSPF /30 Links)")
        link_index = 0
        connections_made = set()
        throughput = delay = jitter = "-"

        for i, pop_i in enumerate(self.config['pops']):
            pop_i_name = pop_i[0]
            for j, pop_j in enumerate(self.config['pops']):
                pop_j_name = pop_j[0]
                
                if i == j or self.config['adjacency_matrix'][i][j] != 1:
                    continue

                edge = tuple(sorted((pop_i_name, pop_j_name)))
                if edge in connections_made:
                    continue
                connections_made.add(edge)

                ri_name = self.pop_to_sname[pop_i_name]
                rj_name = self.pop_to_sname[pop_j_name]
                router_i = self.routers[pop_i_name] 
                router_j = self.routers[pop_j_name]

                if_i = f"{ri_name}{rj_name}"
                if_j = f"{rj_name}{ri_name}"

                router_i.connect(router_j, if_i, if_j)

                ip_i = self.switch_ip_range[link_index]
                ip_j = self.switch_ip_range[link_index+1]
                
                router_i.setIp(ip=ip_i, mask=30, interfaceName=if_i)
                router_j.setIp(ip=ip_j, mask=30, interfaceName=if_j)

                # Inject IP configuraton
                conf_i = f"interface {if_i}\\n ip address {ip_i}/30\\n!"
                conf_j = f"interface {if_j}\\n ip address {ip_j}/30\\n!"
                router_i.run(f"echo -e '{conf_i}' >> /etc/quagga/zebra.conf")
                router_j.run(f"echo -e '{conf_j}' >> /etc/quagga/zebra.conf")

                # Inject OSPF configuration
                ip_parts = ip_i.split('.')
                net_base = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.{int(ip_parts[3]) - 1}"
                
                ospf_net = f"router ospf\\n network {net_base}/30 area 0.0.0.0\\n!"
                router_i.run(f"echo -e '{ospf_net}' >> /etc/quagga/ospfd.conf")
                router_j.run(f"echo -e '{ospf_net}' >> /etc/quagga/ospfd.conf")

                p2p_cmd = "ip ospf network point-to-point\\n!"
                router_i.run(f"echo -e 'interface {if_i}\\n {p2p_cmd}' >> /etc/quagga/ospfd.conf")
                router_j.run(f"echo -e 'interface {if_j}\\n {p2p_cmd}' >> /etc/quagga/ospfd.conf")

                if self.config.get("apply_link_properties"):
                    if self.config.get("randomize_link_properties"):
                        throughput = f"{random.choice(RANDOM_RANGES['throughput'])}mbit"
                        delay = f"{random.choice(RANDOM_RANGES['delay'])}ms"
                        jitter = f"{random.choice(RANDOM_RANGES['jitter'])}ms"
                    else:
                        throughput = self.config["throughput"]
                        delay = self.config["delay"]
                        jitter = self.config["jitter"]

                    router_i.setInterfaceProperties(interfaceName=if_i, throughput=throughput, delay=delay, jitter=jitter)
                    router_j.setInterfaceProperties(interfaceName=if_j, throughput=throughput, delay=delay, jitter=jitter)

                link_index += 2
                print(f"  [OSPF LINK] {pop_i_name} ({ip_i}) <-> {pop_j_name} ({ip_j})")
                time.sleep(0.4)

        print("\n[Experiment] ... Bridging ONOS and Quagga (for UI Discovery)")
        first_pop = self.config['pops'][0][0]
        gw_router = self.routers[first_pop]
        ospf_onos = "router ospf\\n network 172.17.0.0/16 area 0.0.0.0\\n!"
        gw_router.run(f"echo -e '{ospf_onos}' >> /etc/quagga/ospfd.conf")

        print("\n[Experiment] ... Starting Quagga daemons to apply configs")
        for pop, router in self.routers.items():
            router.run("killall -9 zebra ospfd 2>/dev/null || true")
            router.run("/usr/sbin/zebra -d")
            router.run("/usr/sbin/ospfd -d")
            
        print(f"[OK] {len(connections_made)} OSPF inter-PoP links created and configured!\n")

    # Brief: Force host discovery in ONOS by sending ARP/ICMP traffic
    def __run_ping(self) -> None:
        print("\n[DISCOVERY] Forcing host discovery for ONOS...")

        # self.values = {server_name: server_obj}
        for server in self.servers.values():
            print(f"  ... Ping: ALL Servers -> 192.168.0.254") # non-attributed IP addr. Just sends ARP and ONOS discovers it
            server.run(f'bash -lc "ping -c 1 192.168.0.254"')

        # self.clients = {client_name: client_obj}
        for client in self.clients.values():
            print(f"  ... Ping: ALL Clients -> 192.168.0.254")
            client.run(f'bash -lc "ping -c 1 192.168.0.254"')

        print("  ... Discovery packets sent. Waiting 3s for ONOS to process.")
        utils.sleep_countdown(3)
        print("[OK] Hosts should be visible in ONOS.\n")


    def __discover_dash_servers(self) -> None:
        probe_ip = "192.168.0.254"
        print("\n[DISCOVERY] Priming servers (ARP via ping) ...")

        for sname, server in self.servers.items():
            print(f"  ... {sname}: ping {probe_ip}")
            server.run(f'sh -lc "ping -c 1 -W 1 {probe_ip} >/dev/null 2>&1 || true"')
        print("  ... waiting 3s for ONOS /hosts update")
        utils.sleep_countdown(3)
        print("[OK] Servers should be visible in ONOS /hosts.\n")


    # Brief: Run dash-client once on all clients and store results under iter_dir (host path)
    def __run_dash_clients(self, scheme: str = "http"):
        print("\n[DIAG] Running dash-client for all clients (random server each)")

        procs = []
        for cname in self.clients.keys():
            srv = random.choice(self.server_ip_range)
            cmd = (
                f"sudo docker exec {cname} bash -lc "
                f"\"/usr/local/bin/dash-client -y -hostname {srv} -scheme {scheme}\""
            )
            print(f"[DIAG] start {cname} -> server {srv}")
            procs.append(subprocess.Popen(cmd, shell=True))

        for p in procs:
            p.wait()

        print("[DIAG] Done.\n")


    # Brief: Run full topology
    def run(self, run_discovery: bool = False, disable_fwd: bool = False, run_dash_clients: bool = False):
        utils.print_banner()
        
        self.__create_controller()
        c1 = self.controller

        if "1.5" in self.onos_version: # ospf needs quagga routers
            self.__create_routers() 
            self.__connect_routers()
        else:
            self.__create_switches()
            self.__connect_switches()

        if (not self.iperf):
            # Default DASH
            self.__create_clients()
            self.__create_servers()
        if (self.iperf):
            # Only for the iperf experiment!!
            self.__create_clients(iperf=True)
            self.__create_servers(iperf=True)

        self.__discover_dash_servers()

        print("Waiting for network stabilization (5s)...\n")
        utils.sleep_countdown(5)

        if disable_fwd:
            c1.deactivateONOSApps(self.onos_ip)
        else:
            print("[INFO] ONOS Active Forwarding is active (Turn it off if you want to test the deployer).")

        if run_discovery:
            self.__run_ping()
        else:
            print("[INFO] Host discovery (ping) skipped.")

        if run_dash_clients:
            self.__run_dash_clients()
        else:
            print("[INFO] Dash Client script (GET /dash/download/<size>) skipped.")
