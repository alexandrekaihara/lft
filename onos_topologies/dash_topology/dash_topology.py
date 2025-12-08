import os
import random
import subprocess
import time
from pathlib import Path

from . import utils
from .constants import DEFAULT_CONFIG, RANDOM_RANGES
from .dash_client import DashClient
from .dash_server import DashServer
from ..onos import ONOS
from ..switch_modified import Switch


class DashTopology:
    """
    Encapsulates all logic to build, configure and test the topology.
    """

    def __init__(self, 
                 config: dict = DEFAULT_CONFIG, 
                 results_dir: Path = None
                 ):
        self.config = config

        (self.server_ip_range, 
         self.client_ip_range, 
         self.server_pop_names) = self.__get_ip_ranges(self.config["pops"])
        
        # Map: {pop_name: switch_name}
        self.pop_to_sname = {pop[0]: f"s{i}" for i, pop in enumerate(self.config['pops'])}

        # Map: {client_name: client_obj}
        self.clients = {}   

        # Map: {server_name: server_obj}
        self.servers = {}

        # Map: {pop_name: switch_obj}
        self.switches = {}

        # PoP list of client Node (used by collectFlows to select host-facing ports)
        self.hosts_by_pop = {pop[0]: [] for pop in self.config['pops']}

        # Host-side directory that will be bind-mounted into each switch at /results/dash
        self.host_results = Path(results_dir).resolve() if results_dir else None

        self.onos_ip = ""

    # Brief: used to know the servers and clients IP range and switches linked to servers
    def __get_ip_ranges(self, pops: tuple, ip_prefix: str = "192.168.0.") -> tuple:
        tot_num_servers = 0
        tot_num_clients = 0 
        server_pop_names = list() # ex: ["PoP-AC", "PoP-AL", "PoP-AM", ...]

        for pop, num_clients, num_servers in pops:
            if (num_clients):
                tot_num_clients += num_clients
            if (num_servers):
                tot_num_servers += num_servers
                server_pop_names.append(pop)
            
        server_ip_range = [f"{ip_prefix}{i}" for i in range(1, tot_num_servers+1)]
        client_ip_range = [f"{ip_prefix}{i}" for i in range(tot_num_servers+1, tot_num_clients+tot_num_servers+1)]
        return (server_ip_range, client_ip_range, server_pop_names)

    # Brief: Create and configure all DashServer containers
    def __create_servers(self):
        ds_index = 0
        print(f"[Experiment] ... Creating DASH servers")
        for pop, _, num_servers in self.config["pops"]:
            switch_obj = self.switches[pop] # obs: self.switches = {"PoP-AC": switch_AC_obj...}
            for _ in range(num_servers):
                throughput = delay = jitter = "-" # defaults for printing
                dsname = f"ds{ds_index}"
                ds_if = f"{dsname}{self.pop_to_sname[pop]}"
                sw_if = f"{self.pop_to_sname[pop]}{dsname}"

                ds = DashServer(dsname)
                ds.instantiate(mapPorts=False)
                ds.connect(switch_obj, ds_if, sw_if)

                server_ip = self.server_ip_range[ds_index]
                ds.setIp(server_ip, 24, ds_if)
                print(f"  ... Host {dsname} ({server_ip}) created and linked to {pop}")

                if self.config.get("apply_link_properties"):
                    if self.config.get("randomize_link_properties"):
                        throughput = f"{random.choice(RANDOM_RANGES['throughput'])}mbit"
                        delay = f"{random.choice(RANDOM_RANGES['delay'])}ms"
                        jitter = f"{random.choice(RANDOM_RANGES['jitter'])}ms"
                    else:
                        throughput = self.config["throughput"]
                        delay = self.config["delay"]
                        jitter = self.config["jitter"]

                    # TC affects only outgoing traffic on the given interface
                    # Configure both ends to simulate a bidirectional link
                    switch_obj.setInterfaceProperties(interfaceName=sw_if, throughput=throughput, delay=delay, jitter=jitter)
                    ds.setInterfaceProperties(interfaceName=ds_if, throughput=throughput, delay=delay, jitter=jitter)
                    print(f"Throughput={throughput}, Delay={delay}, Jitter={jitter}")
                self.servers[dsname] = ds
                self.hosts_by_pop[pop].append(ds)
                ds_index += 1
        print("[OK] DASH servers created!\n")

    # Brief: Create and configure all DashClient containers
    def __create_clients(self):
        cli_index = 0
        print(f"[Experiment] ... Creating DASH clients")
        for pop, num_clients, _ in self.config["pops"]:
            switch_obj = self.switches[pop] # obs: self.switches = {"PoP-AC": switch_AC_obj...}
            for _ in range(num_clients):
                throughput = delay = jitter = "-" # defaults for printing
                cname = f"cl{cli_index}"
                cl_if = f"{cname}{self.pop_to_sname[pop]}"
                sw_if = f"{self.pop_to_sname[pop]}{cname}"

                cl = DashClient(cname)
                cl.instantiate()
                cl.connect(switch_obj, cl_if, sw_if)

                client_ip = self.client_ip_range[cli_index]
                cl.setIp(client_ip, 24, cl_if)
                print(f"  ... Host {cname} ({client_ip}) created and linked to {pop}")

                if self.config.get("apply_link_properties"):
                    if self.config.get("randomize_link_properties"):
                        throughput = f"{random.choice(RANDOM_RANGES['throughput'])}mbit"
                        delay = f"{random.choice(RANDOM_RANGES['delay'])}ms"
                        jitter = f"{random.choice(RANDOM_RANGES['jitter'])}ms"
                    else:
                        throughput = self.config["throughput"]
                        delay = self.config["delay"]
                        jitter = self.config["jitter"]

                    # TC affects only outgoing traffic on the given interface
                    # Configure both ends to simulate a bidirectional link
                    switch_obj.setInterfaceProperties(interfaceName=sw_if, throughput=throughput, delay=delay, jitter=jitter)
                    cl.setInterfaceProperties(interfaceName=cl_if, throughput=throughput, delay=delay, jitter=jitter)
                    print(f"Throughput={throughput}, Delay={delay}, Jitter={jitter}")
                self.clients[cname] = cl
                self.hosts_by_pop[pop].append(cl)
                cli_index += 1
        print("[OK] DASH clients created!\n")

    # Brief: Create the ONOS controller, start it and activate required apps
    def __create_controller(self):
        print("\n[Experiment] ... Creating ONOS controller")
        c1 = ONOS("c1")
        c1.instantiate(mapPorts=True)
        self.onos_ip = utils.get_container_ip("c1")
        print(f"[CTRL] ONOS IP: {self.onos_ip}")
        print("Waiting for ONOS to initialize (30s) ...")
        utils.sleep_countdown(30)
        print("[CTRL] Activating OpenFlow + Host Provider + Reactive Forwarding")
        c1.activateONOSApps(self.onos_ip)
        print("[OK] ONOS is ready!\n")

    # Brief: Create all OVS switches and connect them to the ONOS controller
    def __create_switches(self):
        if self.host_results is None:
            self.host_results = Path(os.getenv("LFT_RESULTS", "/lft/results/dash")).resolve()
            self.host_results.mkdir(parents=True, exist_ok=True)

        print(f"[Experiment] ... Creating {len(self.config['pops'])} OVS switches")
        for pop, sname in self.pop_to_sname.items():
            sw = Switch(sname, hostPath=str(self.host_results), containerPath="/results/dash")
            sw.instantiate(image='alexandremitsurukaihara/lst2.0:openvswitch', networkMode="bridge")
            self.switches[pop] = sw
            print(f"  ... Switch {pop} as {sname} was created!")
            time.sleep(0.4)

        print(f"[CTRL] Pointing all switches to ONOS ({self.onos_ip}:6653)")
        for pop, *_ in self.config['pops']:
            self.switches[pop].setController(self.onos_ip, 6653)
        print("[OK] Controllers configured!\n")

    # Brief: Create PoP links based on self.config['adjacency_matrix']
    def __connect_switches(self):
        print("[Experiment] ... Connecting PoP-to-PoP switches")
        connections_made = set()

        for i, pop_i in enumerate(self.config['pops']):
            pop_i_name = pop_i[0]       # ex: pop_i_name = "PoP-AC"; pop_i = ("PoP-AC", 0, 1)
            for j, pop_j in enumerate(self.config['pops']):
                pop_j_name = pop_j[0]   # ex: pop_j_name = "PoP-CE"; pop_j = ("PoP-CE", 5, 0)
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

                print(f"  [LINK] {pop_i_name} <-> {pop_j_name}")
                time.sleep(0.4)

        print(f"[OK] {len(connections_made)} inter-PoP links created!\n")

    # Brief: Force host discovery in ONOS by sending ARP/ICMP traffic
    def __run_ping(self) -> None:
        print("\n[DISCOVERY] Forcing host discovery for ONOS...")
        first_client_ip = self.client_ip_range[0]
        first_server_ip = self.server_ip_range[0]

        # self.values = {server_name: server_obj}
        for server in self.servers.values():
            print(f"  ... Ping: ALL Servers -> Client ({first_client_ip})")
            server.run(f'bash -lc "ping -c 1 {first_client_ip}"')

        # self.clients = {client_name: client_obj}
        for client in self.clients.values():
            print(f"  ... Ping: ALL Clients -> Server ({first_server_ip})")
            client.run(f'bash -lc "ping -c 1 {first_server_ip}"')

        print("  ... Discovery packets sent. Waiting 3s for ONOS to process.")
        utils.sleep_countdown(3)
        print("[OK] Hosts should be visible in ONOS.\n")

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
    def run(self, run_discovery: bool = False, run_dash_clients: bool = False):
        utils.print_banner()

        self.__create_controller()
        self.__create_switches()
        self.__connect_switches()
        self.__create_clients()
        self.__create_servers()

        print("Waiting for network stabilization (5s)...\n")
        utils.sleep_countdown(5)

        if run_discovery:
            self.__run_ping()
        else:
            print("[INFO] Host discovery (ping) skipped.")

        if run_dash_clients:
            self.__run_dash_clients()
        else:
            print("[INFO] Dash Client script (GET /dash/download/<size>) skipped.")
