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
    Encapsulates all logic to build, configure, and test the topology.
    """

    def __init__(self, config: dict = DEFAULT_CONFIG, results_dir: Path = None):
        # Store user configuration
        self.config = config

        print("[INFO] Initializing topology with the following parameters:")
        print(f"  - Hosts per PoP: {self.config['hosts_per_pop']}")
        print(f"  - Server PoP: {self.config['server_pop']}")
        print(f"  - Server IP: {self.config['server_ip']}")
        print(f"  - Client start IP octet: 192.168.0.{self.config['client_ip_start']}")

        self.n_hosts_per_pop = self.config["hosts_per_pop"]
        self.server_pop_name = self.config["server_pop"]
        self.server_ip = self.config["server_ip"]
        self.client_start_octet = self.config["client_ip_start"]

        # PoP list of client Node (used by collectFlows to select host-facing ports)
        self.clients_by_pop = {pop: [] for pop in self.config['pops']}

        self.onos_ip = ""
        self.switches = {}  # Map: {pop_name: Switch_obj}
        self.clients = {}   # Map: {client_name: DashClient_obj}
        self.server = None

        # Map: {client_name: interface_name}
        self.client_ifnames = {}

        # Host-side directory that will be bind-mounted into each switch at /results/dash
        self.host_results = Path(results_dir)

        # Map: {pop_name: switch_name}
        self.pop_to_switch_name = {pop: f"s{i}" for i, pop in enumerate(self.config['pops'])}

        # Argument validation
        if self.server_pop_name not in self.config['pops']:
            raise ValueError(f"[ERROR] Server PoP '{self.server_pop_name}' does not exist in the POPS list.")
        if self.client_start_octet + (len(self.config['pops']) * self.n_hosts_per_pop) > 254:
            raise ValueError(
                f"[ERROR] Combination of hosts per PoP ({self.n_hosts_per_pop}) and starting IP "
                f"({self.client_start_octet}) exceeds the IP limit (254)."
            )

    # Brief: Create the ONOS controller, start it, and activate required apps
    def _setup_controller(self):
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
    def _setup_switches(self):
        if self.host_results is None:
            self.host_results = Path(os.getenv("LFT_RESULTS", "/lft/results/dash")).resolve()
            self.host_results.mkdir(parents=True, exist_ok=True)

        print(f"[Experiment] ... Creating {len(self.config['pops'])} OVS switches")
        for pop, sname in self.pop_to_switch_name.items():
            sw = Switch(sname, hostPath=str(self.host_results), containerPath="/results/dash")
            sw.instantiate(image='alexandremitsurukaihara/lst2.0:openvswitch', networkMode="bridge")
            self.switches[pop] = sw
            print(f"  ... Switch {pop} as {sname} was created!")
            time.sleep(0.4)

        print(f"[CTRL] Pointing all switches to ONOS ({self.onos_ip}:6653)")
        for pop in self.config['pops']:
            self.switches[pop].setController(self.onos_ip, 6653)
        print("[OK] Controllers configured!\n")

    # Brief: Create PoP links based on self.config['adjacency_matrix']
    def _connect_switches(self):
        print("[Experiment] ... Connecting PoP-to-PoP switches")
        connections_made = set()

        for i, pop_i in enumerate(self.config['pops']):
            for j, pop_j in enumerate(self.config['pops']):
                if i == j:
                    continue
                if self.config['adjacency_matrix'][i][j] != 1:
                    continue

                edge = tuple(sorted((pop_i, pop_j)))
                if edge in connections_made:
                    continue
                connections_made.add(edge)

                si = self.pop_to_switch_name[pop_i]
                sj = self.pop_to_switch_name[pop_j]
                self.switches[pop_i].connect(self.switches[pop_j], f"{si}{sj}", f"{sj}{si}")

                print(f"  [LINK] {pop_i} <-> {pop_j}")
                time.sleep(0.4)

        print(f"[OK] {len(connections_made)} inter-PoP links created!\n")

    # Brief: Create all clients and the DASH server, connect them to their PoP switches, and start collectors
    def _setup_hosts(self):
        print(f"[Experiment] ... Creating {self.n_hosts_per_pop} client(s) per PoP")
        self._create_clients()
        print("[OK] DASH clients created!\n")

        print("[Experiment] ... Creating DASH server")
        self.server = DashServer("ds1")
        self.server.instantiate(mapPorts=False)

        print(f"[Experiment] ... Connecting server to {self.server_pop_name}")
        s_server = self.pop_to_switch_name[self.server_pop_name]
        ds1_if = f"ds1{s_server}"
        s_server_if = f"{s_server}ds1"

        self.server.connect(self.switches[self.server_pop_name], ds1_if, s_server_if)
        print(f"  [LINK] ds1 <-> {self.server_pop_name} ({s_server})")

        print("[IP] Configuring host IPs")
        self.server.setIp(self.server_ip, 24, ds1_if)
        print(f"  [IP] Server ds1: {self.server_ip}")
        print("[OK] Host links created and IPs configured!\n")


    # Brief: Create and configure all DashClient containers
    def _create_clients(self):
        cli_index = 0
        ip_octet = self.client_start_octet

        randomize = self.config["randomize_link_properties"]
        print(f"[QoS] Randomization is {'ON' if randomize else 'OFF'}.")

        for pop, switch in self.switches.items():
            for _ in range(self.n_hosts_per_pop):
                cname = f"cl{cli_index}"
                cl_if = f"{cname}{self.pop_to_switch_name[pop]}"
                sw_if = f"{self.pop_to_switch_name[pop]}{cname}"

                cl = DashClient(cname)
                cl.instantiate()
                cl.connect(switch, cl_if, sw_if)

                client_ip = f"192.168.0.{ip_octet}"
                cl.setIp(client_ip, 24, cl_if)

                if randomize:
                    throughput = f"{random.choice(RANDOM_RANGES['throughput'])}mbit"
                    delay = f"{random.choice(RANDOM_RANGES['delay'])}ms"
                    jitter = f"{random.choice(RANDOM_RANGES['jitter'])}ms"
                else:
                    throughput = self.config["throughput"]
                    delay = self.config["delay"]
                    jitter = self.config["jitter"]

                # TC affects only outgoing traffic on the given interface
                # Configure both ends to emulate a bidirectional link
                switch.setInterfaceProperties(interfaceName=sw_if, throughput=throughput, delay=delay, jitter=jitter)
                cl.setInterfaceProperties(interfaceName=cl_if, throughput=throughput, delay=delay, jitter=jitter)

                self.clients[cname] = cl
                self.clients_by_pop[pop].append(cl)
                self.client_ifnames[cname] = cl_if

                print(
                    f"  ... Host {cname} ({client_ip}) created and linked to {pop} with (QoS): "
                    f"Throughput={throughput}, Delay={delay}, Jitter={jitter}"
                )

                ip_octet += 1
                cli_index += 1


    # Brief: Force host discovery in ONOS by sending ARP/ICMP traffic
    def _run_discovery(self):
        print("\n[DISCOVERY] Forcing host discovery for ONOS...")

        first_client_ip = f"192.168.0.{self.client_start_octet}"
        print(f"  ... Ping: Server ({self.server_ip}) -> Client ({first_client_ip})")
        self.server.run(f'bash -lc "ping -c1 -W1 {first_client_ip}"')

        print(f"  ... Ping: ALL Clients -> Server ({self.server_ip})")
        for client_obj in self.clients.values():
            client_obj.run(f'bash -lc "ping -c1 -W1 {self.server_ip}"')

        print("  ... Discovery packets sent. Waiting 3s for ONOS to process.")
        utils.sleep_countdown(3)
        print("[OK] Hosts should be visible in ONOS.\n")


    # Brief: Run dash-client once on all clients and store results under iter_dir (host path)
    def run_diagnostics_round(self, iter_dir: str, scheme: str = "http"):
        iter_path = Path(iter_dir)
        clients_path = iter_path / "clients"
        clients_path.mkdir(parents=True, exist_ok=True)

        print(f"\n[DIAG] Running DASH diagnostics round -> {iter_path}")

        host_datadir_root = Path(os.environ["LFT_RESULTS"]).resolve()
        daydir = time.strftime("%Y/%m/%d", time.gmtime())
        default_dir = host_datadir_root / "dash" / daydir
        default_dir.mkdir(parents=True, exist_ok=True)

        # Snapshot existing files once
        known = {p.name for p in default_dir.glob("*.json.gz")}

        for cname in self.clients.keys():
            out_host = clients_path / f"{cname}.json.gz"

            run_cmd = (
                f"sudo docker exec {cname} bash -lc "
                f"\"/usr/local/bin/dash-client -y -hostname {self.server_ip} -scheme {scheme}\""
            )
            print(f"[DIAG] {cname}: dash-client -> {out_host}")
            subprocess.run(run_cmd, shell=True, check=False)

            newest = None
            for _ in range(50):  # ~5s total (50 * 0.1)
                candidates = [p for p in default_dir.glob("*.json.gz") if p.name not in known]
                if candidates:
                    newest = max(candidates, key=lambda p: p.stat().st_mtime)
                    break
                time.sleep(0.1)

            if newest:
                known.add(newest.name)
                newest.replace(out_host) 
            else:
                print(f"[WARNING] No NEW output found for {cname} in {default_dir}")

        print("[DIAG] Round finished.\n")


    # Brief: Execute full topology setup
    def run(self, skip_discovery: bool = False):
        utils.print_banner()

        self._setup_controller()
        self._setup_switches()
        self._connect_switches()
        self._setup_hosts()

        print("Waiting for network stabilization (5s)...\n")
        utils.sleep_countdown(5)

        if not skip_discovery:
            self._run_discovery()
        else:
            print("[INFO] Host discovery (ping-all) skipped.")
