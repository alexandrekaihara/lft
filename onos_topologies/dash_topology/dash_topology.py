import os
import random
import subprocess
import time
import glob
from pathlib import Path

from . import utils
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

        (self.switch_ip_range,
         self.server_ip_range, 
         self.client_ip_range, 
         self.server_pop_names) = self.__get_ip_ranges(self.config["pops"])
        
        # Only created for the iperf experiment. If true, clients and servers use iperf instead of the typical dash algo
        self.iperf = iperf  

        # Default version v2.5 for compatibility with measuring tools
        self.onos_version = onos_version

        # Map: {pop_name: switch_name}
        self.pop_to_sname = {pop[0]: f"s{i}" for i, pop in enumerate(self.config['pops'])}

        # Map: {client_name: client_obj}
        self.clients = {}   

        # Map: {server_name: server_obj}
        self.servers = {}

        # Map: {pop_name: switch_obj}
        self.switches = {}

        # ONOS controller (object)
        self.controller = ""

        # PoP list of client Node (used by collectFlows to select host-facing ports)
        self.hosts_by_pop = {pop[0]: [] for pop in self.config['pops']}

        # Host-side directory that will be bind-mounted into each switch at /results/dash
        self.host_results = Path(results_dir).resolve() if results_dir else None

        self.onos_ip = ""

    # Brief: used to know the servers and clients IP range and switches linked to servers
    def __get_ip_ranges(self, pops: tuple, ip_prefix: str = "192.168.0.") -> tuple:
        tot_num_switches = 0 # switches receive a 'special IP' only for RTT measuring 
        tot_num_servers = 0
        tot_num_clients = 0 
        server_pop_names = list() # ex: ["PoP-AC", "PoP-AL", "PoP-AM", ...]

        for pop, num_clients, num_servers in pops:
            if (pop):
                tot_num_switches += 1
            if (num_clients):
                tot_num_clients += num_clients
            if (num_servers):
                tot_num_servers += num_servers
                server_pop_names.append(pop)
            
        # 2 IPs per inter-switch link for RTT probe only
        max_links = tot_num_switches * (tot_num_switches - 1) // 2
        switch_ip_range = []
        for k in range(max_links): # generates 2 * num_switches IPs,all valid in /30 mask
            base = 4 * k
            switch_ip_range.append(f"10.0.0.{base + 1}")
            switch_ip_range.append(f"10.0.0.{base + 2}")

        server_ip_range = [f"{ip_prefix}{i}" for i in range(1, tot_num_servers+1)]
        client_ip_range = [f"{ip_prefix}{i}" for i in range(tot_num_servers+1, tot_num_clients+tot_num_servers+1)]
        return (switch_ip_range, server_ip_range, client_ip_range, server_pop_names)

    # Brief: Create and configure all DashServer containers
    def __create_servers(self, iperf=False):
        ds_index = 0
        print(f"[Experiment] ... Creating DASH servers")
        for pop, _, num_servers in self.config["pops"]:
            switch_obj = self.switches[pop] # obs: self.switches = {"PoP-AC": switch_AC_obj...}
            for _ in range(num_servers):
                throughput = delay = jitter = "-" # defaults for printing
                dsname = f"ds{ds_index}"
                ds_if = f"{dsname}{self.pop_to_sname[pop]}"
                sw_if = f"{self.pop_to_sname[pop]}{dsname}"

                if (not iperf):
                    ds = DashServer(dsname)
                else:
                    ds = IperfServer(dsname)
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
    def __create_clients(self, iperf=False):
        cli_index = 0
        print(f"[Experiment] ... Creating DASH clients")
        for pop, num_clients, _ in self.config["pops"]:
            switch_obj = self.switches[pop] # obs: self.switches = {"PoP-AC": switch_AC_obj...}
            for _ in range(num_clients):
                throughput = delay = jitter = "-" # defaults for printing
                cname = f"cl{cli_index}"
                cl_if = f"{cname}{self.pop_to_sname[pop]}"
                sw_if = f"{self.pop_to_sname[pop]}{cname}"

                if (not iperf):
                    cl = DashClient(cname)
                else:
                    cl = IperfClient(cname)
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
        dockerImage=self.onos_version
        c1.instantiate(dockerImage=dockerImage, mapPorts=True) 
        self.onos_ip = utils.get_container_ip("c1")
        c1.setCliIp(self.onos_ip) # needed in runOnosCliCommands() from Onos class
        print(f"[CTRL] ONOS IP: {self.onos_ip}")
        print("Waiting for ONOS to initialize (30s) ...")
        utils.sleep_countdown(30)
        print("[CTRL] Activating OpenFlow + Host Provider + Reactive Forwarding")
        c1.activateONOSApps(self.onos_ip)

        if (dockerImage == "onosproject/onos:2.5.0"):
            print("[CTRL] Installing custom latency app via REST API...")
            
            current_dir = os.path.dirname(os.path.abspath(__file__))
            search_path = os.path.join(current_dir, "..", "*.oar")
            oar_files = glob.glob(search_path)
            
            if not oar_files:
                print("[ERROR] .oar file not found!")
                return 

            oar_path = oar_files[0]
            container_name = "c1"

            # Copy to ONOS container home
            subprocess.run(f"docker cp {oar_path} {container_name}:/home/onos/lft_app.oar", shell=True)

            # Permissions to run the .oar (Chown and Chmod)
            subprocess.run(f"docker exec -u 0 {container_name} chown onos:onos /home/onos/lft_app.oar", shell=True)
            subprocess.run(f"docker exec -u 0 {container_name} chmod 644 /home/onos/lft_app.oar", shell=True)

            # Install and activate via REST API
            activation_cmd = (
                f'docker exec {container_name} curl -u onos:rocks -X POST '
                f'-H "Content-Type:application/octet-stream" '
                f'"http://localhost:8181/onos/v1/applications?activate=true" '
                f'--data-binary "@/home/onos/lft_app.oar"'
            )
            subprocess.run(activation_cmd, shell=True)
            
            print("[OK] Latency app installed and activated!")
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

    # Brief: Create PoP links based on self.config['adjacency_matrix']
    def __connect_switches(self):
        print("[Experiment] ... Connecting PoP-to-PoP switches")
        sw_index = 0
        connections_made = set()
        throughput = delay = jitter = "-" # defaults for printing

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

                """
                # Attribute 10.0.0.X IP addr for RTT measurements
                si_obj = self.switches[pop_i_name]
                sj_obj = self.switches[pop_j_name]

                si_ip = self.switch_ip_range[sw_index]
                sj_ip = self.switch_ip_range[sw_index+1]

                si_obj.setIp(ip=si_ip, mask=30, interfaceName=f"{si}{sj}")
                print(f"  {pop_i_name} received {si_ip} IP addr on {si}{sj} IF (for RTT measurements)")

                sj_obj.setIp(ip=sj_ip, mask=30, interfaceName=f"{sj}{si}")
                print(f"  {pop_j_name} received {sj_ip} IP addr on {sj}{si} IF (for RTT measurements)")

                # Allow switches to communicate with each other
                self.__add_frules_for_measurements(
                    si=si,
                    sj=sj,
                    si_ip=si_ip,
                    sj_ip=sj_ip,
                    if_i=f"{si}{sj}",
                    if_j=f"{sj}{si}",
                )

                sw_index += 2
                """

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

    # Brief: switches shall ping to each other to discover RTT. 
    # Add flow rules without fwd to allow this traffic
    def __add_frules_for_measurements(self, si: str, sj: str, si_ip: str, sj_ip: str, if_i: str, if_j: str) -> None:
        try:
            def dsh(sw: str, *cmd: str) -> str:
                return subprocess.check_output(["docker", "exec", sw, *cmd], text=True).strip()

            def dcall(sw: str, *cmd: str) -> None:
                subprocess.check_call(["docker", "exec", sw, *cmd])

            def get_ofport(sw: str, iface: str) -> str:
                ofp = dsh(sw, "ovs-vsctl", "get", "Interface", iface, "ofport").strip()
                if ofp in ("", "-1"):
                    raise RuntimeError(f"Invalid ofport for {sw}:{iface}: {ofp}")
                return ofp

            def get_dpid(sw: str) -> str:
                res = dsh(sw, "ovs-vsctl", "get", "bridge", sw, "datapath_id").strip().strip('"')
                return f"of:{res}"

            def mac_of(sw: str, dev: str) -> str:
                return dsh(sw, "cat", f"/sys/class/net/{dev}/address").strip()

            # Link ofports
            of_i = get_ofport(si, if_i)
            of_j = get_ofport(sj, if_j)

            # Use LOCAL for measurements
            dcall(si, "ip", "link", "set", si, "up")
            dcall(sj, "ip", "link", "set", sj, "up")

            # Add /32 on the bridge if not already there
            try: dcall(si, "ip", "addr", "add", f"{si_ip}/32", "dev", si)
            except: pass
            try: dcall(sj, "ip", "addr", "add", f"{sj_ip}/32", "dev", sj)
            except: pass

            # Force kernel to use LOCAL
            dcall(si, "ip", "route", "replace", f"{sj_ip}/32", "dev", si)
            dcall(sj, "ip", "route", "replace", f"{si_ip}/32", "dev", sj)

            # Static neigh so kernel emits ETH_DST = peer bridge MAC
            mac_i = mac_of(si, si) # bridge MAC
            mac_j = mac_of(sj, sj) # bridge MAC
            dcall(si, "ip", "neigh", "replace", sj_ip, "lladdr", mac_j, "dev", si, "nud", "permanent")
            dcall(sj, "ip", "neigh", "replace", si_ip, "lladdr", mac_i, "dev", sj, "nud", "permanent")

            dpid_i = get_dpid(si)
            dpid_j = get_dpid(sj)

            # Switch si: LOCAL -> link (towards sj)
            crit_i_out = [
                {"type": "ETH_TYPE", "ethType": "0x0800"},
                {"type": "ETH_SRC", "mac": mac_i},
                {"type": "ETH_DST", "mac": mac_j},
                {"type": "IPV4_SRC", "ip": f"{si_ip}/32"},
                {"type": "IPV4_DST", "ip": f"{sj_ip}/32"},
            ]
            utils.push_onos_flow(self.onos_ip, dpid_i, crit_i_out, of_i, priority=60000)

            # Switch si: link -> LOCAL (from sj)
            crit_i_in = [
                {"type": "ETH_TYPE", "ethType": "0x0800"},
                {"type": "IN_PORT", "port": str(of_i)},  
                {"type": "ETH_SRC", "mac": mac_j},
                {"type": "ETH_DST", "mac": mac_i},
                {"type": "IPV4_SRC", "ip": f"{sj_ip}/32"},
                {"type": "IPV4_DST", "ip": f"{si_ip}/32"},
            ]
            utils.push_onos_flow(self.onos_ip, dpid_i, crit_i_in, "LOCAL", priority=60000)

            # Switch sj: LOCAL -> link (towards si)
            crit_j_out = [
                {"type": "ETH_TYPE", "ethType": "0x0800"},
                {"type": "ETH_SRC", "mac": mac_j},
                {"type": "ETH_DST", "mac": mac_i},
                {"type": "IPV4_SRC", "ip": f"{sj_ip}/32"},
                {"type": "IPV4_DST", "ip": f"{si_ip}/32"},
            ]
            utils.push_onos_flow(self.onos_ip, dpid_j, crit_j_out, of_j, priority=60000)

            # Switch sj: link -> LOCAL (from si)
            crit_j_in = [
                {"type": "ETH_TYPE", "ethType": "0x0800"},
                {"type": "IN_PORT", "port": str(of_j)},    
                {"type": "ETH_SRC", "mac": mac_i},
                {"type": "ETH_DST", "mac": mac_j},
                {"type": "IPV4_SRC", "ip": f"{si_ip}/32"},
                {"type": "IPV4_DST", "ip": f"{sj_ip}/32"},
            ]
            utils.push_onos_flow(self.onos_ip, dpid_j, crit_j_in, "LOCAL", priority=60000)

            print(f"  [RTT-FLOWS] L2-style flows pushed for {si} <-> {sj}")

        except Exception as e:
            print(f"  [RTT-FLOWS] failed on {si}<->{sj}: {e}")

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
            # usa sh (debian slim não garante bash)
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
