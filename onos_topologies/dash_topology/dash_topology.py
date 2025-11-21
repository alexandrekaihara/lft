import subprocess
import time
import random
from pathlib import Path
from . import utils
from .dash_server import DashServer
from .dash_client import DashClient
from ..switch_modified import Switch
from ..onos import ONOS
from .constants import POPS, ADJACENCY_MATRIX, DEFAULT_CONFIG, RANDOM_RANGES

class DashTopology:
    """
    Brief: Encapsulates all the logic to build, configure and test the topology
    """
    def __init__(self, config:dict=DEFAULT_CONFIG):
        
        # Merge user configuration with defaults
        self.config = config

        print("[INFO] Initializing topology with the following parameters:")
        print(f"  - Hosts per PoP: {self.config['hosts_per_pop']}")
        print(f"  - Server PoP: {self.config['server_pop']}")
        print(f"  - Server IP: {self.config['server_ip']}")
        print(f"  - Client start IP octet: 192.168.0.{self.config['client_ip_start']}")

        self.n_hosts_per_pop = self.config['hosts_per_pop']
        self.server_pop_name = self.config['server_pop']
        self.server_ip = self.config['server_ip']
        self.client_start_octet = self.config['client_ip_start']
        
        self.onos_ip = ""
        self.switches = {}  # Map: {pop_name: Switch_obj}
        self.clients = {}   # Map: {client_name: DashClient_obj}
        self.server = None

        # Map: {client_name: interface_name}
        self.client_ifnames = {}

        # Map: {pop_name: switch_name}
        self.pop_to_switch_name = {pop: f"s{i}" for i, pop in enumerate(POPS)}

        # Argument validation
        if self.server_pop_name not in POPS:
            raise ValueError(f"[ERROR] Server PoP '{self.server_pop_name}' does not exist in the POPS list.")
        if self.client_start_octet + (len(POPS) * self.n_hosts_per_pop) > 254:
            raise ValueError(f"[ERROR] Combination of hosts per PoP ({self.n_hosts_per_pop}) and starting IP ({self.client_start_octet}) exceeds the IP limit (254).")


    # Brief: Creates the ONOS controller, starts it and activates necessary apps
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


    # Brief: Creates all OVS switches and connects them to the ONOS controller
    def _setup_switches(self):
        print(f"[Experiment] ... Creating {len(POPS)} OVS switches")
        for pop, sname in self.pop_to_switch_name.items():
            sw = Switch(sname)
            # Runs OVS container on (172.17.0.x)
            sw.instantiate(networkMode="bridge")
            self.switches[pop] = sw
            time.sleep(0.4)
        
        print(f"[CTRL] Pointing all switches to ONOS ({self.onos_ip}:6653)")
        for pop in POPS:
            self.switches[pop].setController(self.onos_ip, 6653)
        print("[OK] Controllers configured!\n")


    # Brief: Creates inter-PoP links based on the ADJACENCY_MATRIX
    def _connect_switches(self):
        print("[Experiment] ... Connecting PoP-to-PoP switches")
        connections_made = set()
        for i, pop_i in enumerate(POPS):
            for j, pop_j in enumerate(POPS):
                if i != j and ADJACENCY_MATRIX[i][j] == 1:
                    edge = tuple(sorted((pop_i, pop_j)))
                    if edge in connections_made:
                        continue
                    connections_made.add(edge)
                    si, sj = self.pop_to_switch_name[pop_i], self.pop_to_switch_name[pop_j]
                    self.switches[pop_i].connect(self.switches[pop_j], f"{si}{sj}", f"{sj}{si}")
                    print(f"  [LINK] {pop_i} <-> {pop_j}")
                    time.sleep(0.4)
        print(f"[OK] {len(connections_made)} inter-PoP links created!\n")
    

    # Brief: Creates all client hosts and the DASH server and connects them to their respective PoP switches
    def _setup_hosts(self):
        print(f"[Experiment] ... Creating {self.n_hosts_per_pop} client(s) per PoP")
        self._create_clients()
        print("[OK] DASH clients created!\n")

        print("[Experiment] ... Creating DASH server")
        self.server = DashServer("ds1")
        self.server.instantiate(mapPorts=False)

        print(f"[Experiment] ... Connecting server to {self.server_pop_name}")
        s_server = self.pop_to_switch_name[self.server_pop_name]
        ds1_if = f"ds1{s_server}"; s_server_if = f"{s_server}ds1"
        
        self.server.connect(self.switches[self.server_pop_name], ds1_if, s_server_if)
        print(f"  [LINK] ds1 <-> {self.server_pop_name} ({s_server})")
        
        print("[IP] Configuring host IPs")
        self.server.setIp(self.server_ip, 24, ds1_if)
        print(f"  [IP] Server ds1: {self.server_ip}")
        print("[OK] Host links created and IPs configured!\n")


    # Brief: Internal method to create and configure all DashClient containers
    def _create_clients(self):
        cli_index = 0
        ip_octet = self.client_start_octet
        
        # Link properties decision (QoS)
        randomize = self.config["randomize_link_properties"] # True or False
        print(f"[QoS] Randomization is {'ON' if randomize else 'OFF'}.")

        for POP, switch in self.switches.items():
            for i in range(self.n_hosts_per_pop):
                cname = f"cl{cli_index}"
                cl_if = f"{cname}{self.pop_to_switch_name[POP]}"
                sw_if = f"{self.pop_to_switch_name[POP]}{cname}"
                
                cl = DashClient(cname); cl.instantiate()
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

                cl.setInterfaceProperties(
                    interfaceName=cl_if,
                    throughput=throughput,
                    delay=delay,
                    jitter=jitter
                )

                self.clients[cname] = cl
                self.client_ifnames[cname] = cl_if
                print(f"  ... Host {cname} ({client_ip}) created and linked to {POP} with (QoS): Throughput={throughput}, Delay={delay}, Jitter={jitter}")
                
                ip_octet += 1
                cli_index += 1


    # Brief: Forces all hosts to send an ARP packet to be discovered by ONOS
    def _run_discovery(self):
        print("\n[DISCOVERY] Forcing host discovery for ONOS...")
        
        # Discover the Server (by pinging the first client)
        first_client_ip = f"192.168.0.{self.client_start_octet}"
        print(f"  ... Ping: Server ({self.server_ip}) -> Client ({first_client_ip})")
        # -c1 = 1 packet, -W1 = 1s timeout
        self.server.run(f'bash -lc "ping -c1 -W1 {first_client_ip}"')
        
        # Discover ALL Clients (by pinging the server)
        print(f"  ... Ping: ALL Clients -> Server ({self.server_ip})")
        for client_obj in self.clients.values():
            client_obj.run(f'bash -lc "ping -c1 -W1 {self.server_ip}"')

        print("  ... Discovery packets sent. Waiting 3s for ONOS to process.")
        utils.sleep_countdown(3)
        print("[OK] Hosts should be visible in ONOS.\n")


    # Brief: Executes basic connectivity tests (ping/curl) from the first client to the server
    def _run_tests(self):
        test_cli_name = next(iter(self.clients.keys()))
        tcli = self.clients[test_cli_name]
        print(f"\n[TEST] Running quick tests using client {test_cli_name}...")
        # Ping from client to DASH server
        print(f"[TEST] Ping: {test_cli_name} -> Server ({self.server_ip})")
        print(
            tcli.run(
                f'bash -lc "ping -c3 {self.server_ip}"'
            ).stdout.read()
        )
        # HTTP curl to /negotiate/dash
        print(f"[TEST] Curl (HTTP): {test_cli_name} -> Server ({self.server_ip})")
        print(
            tcli.run(
                f'bash -lc "curl -v --max-time 5 http://{self.server_ip}/negotiate/dash"'
            ).stdout.read()
        )
        # HTTPS curl to /negotiate/dash
        print(f"[TEST] Curl (HTTPS): {test_cli_name} -> Server ({self.server_ip})")
        print(
            tcli.run(
                f'bash -lc "curl -v --max-time 5 https://{self.server_ip}/negotiate/dash"'
            ).stdout.read()
        )
        # Dump flow entries on the server's switch
        s_server = self.pop_to_switch_name[self.server_pop_name]
        print(f"[TEST] Checking flow counters on server switch ({s_server})")
        subprocess.run(
            f"docker exec {s_server} ovs-ofctl -O OpenFlow13 dump-flows {s_server}",
            shell=True,
            check=False
        )
        # Run full DASH experiment over HTTP
        print(f"[TEST] Running Full DASH Experiment (HTTP): {test_cli_name} -> Server ({self.server_ip})")
        dash_http = tcli.run(
            f'bash -lc "dash-client -y -hostname {self.server_ip} -scheme http"'
        )
        print(dash_http.stdout.read())
        # Dump flows after HTTP DASH experiment
        print(f"[TEST] Checking flow counters on server switch ({s_server}) after HTTP DASH")
        subprocess.run(
            f"docker exec {s_server} ovs-ofctl -O OpenFlow13 dump-flows {s_server}",
            shell=True,
            check=False
        )
        # Run full DASH experiment over HTTPS
        print(f"[TEST] Running Full DASH Experiment (HTTPS): {test_cli_name} -> Server ({self.server_ip})")
        dash_https = tcli.run(
            f'bash -lc "dash-client -y -hostname {self.server_ip} -scheme https"'
        )
        print(dash_https.stdout.read())
        # Dump flows after HTTPS DASH experiment
        print(f"[TEST] Checking flow counters on server switch ({s_server}) after HTTPS DASH")
        subprocess.run(
            f"docker exec {s_server} ovs-ofctl -O OpenFlow13 dump-flows {s_server}",
            shell=True,
            check=False
        )
        print("[OK] All tests concluded.\n")


    # Brief: Inspect QoS settings for a few clients    
    # It checks:
    #   - tc qdisc configuration and statistics
    #   - ICMP RTT
    def _run_qos_diagnostics(self, max_clients: int = 3):
        if not self.clients:
            print("[QOS] No clients available to run QoS diagnostics.")
            return

        print("\n[QOS] Running QoS diagnostics...")

        # Limit how many clients are inspected
        selected_clients = list(self.clients.keys())[:max_clients]

        for cname in selected_clients:
            client = self.clients[cname]
            cl_if = self.client_ifnames.get(cname)

            print(f"\n[QOS] Client: {cname}")
            print(f"      Interface: {cl_if}")

            # Show tc qdisc configuration and counters
            print("[QOS] tc qdisc stats on client interface:")
            tc_output = client.run(
                f'bash -lc "tc -s qdisc show dev {cl_if}"'
            ).stdout.read()
            print(tc_output)

            # Measure ICMP RTT statistics (approx delay/jitter)
            print("[QOS] Measuring ICMP RTT (ping) to server:")
            ping_output = client.run(
                f'bash -lc "ping -c 20 -i 0.2 {self.server_ip}"'
            ).stdout.read()
            print(ping_output)

        print("\n[QOS] QoS diagnostics finished.\n")


    # Brief: Runs dash-client on ALL clients once and stores results under iter_dir.
    # iter_dir: it's the path on the HOST where results will be stored
    def run_diagnostics_round(self, iter_dir: str, scheme: str = "http"):
        iter_path = Path(iter_dir)
        clients_path = iter_path / "clients"
        clients_path.mkdir(parents=True, exist_ok=True)

        print(f"\n[DIAG] Running DASH diagnostics round -> {iter_path}")

        # find the host datadir root from iter_dir
        parts = iter_path.parts
        if "datadir" in parts:
            idx = parts.index("datadir")
            host_datadir_root = Path(*parts[:idx+1])  # .../datadir
        else:
            host_datadir_root = iter_path.parent      

        # default directory where the server saves today (UTC)
        daydir = time.strftime("%Y/%m/%d", time.gmtime())
        default_dir = host_datadir_root / "dash" / daydir
        default_dir.mkdir(parents=True, exist_ok=True)

        for cname in self.clients.keys():
            out_host = clients_path / f"{cname}.json.gz"

            # clean only todayss default output on the HOST
            for f in default_dir.glob("*.json.gz"):
                f.unlink(missing_ok=True)

            # run dash-client inside the client container
            run_cmd = (
                f"sudo docker exec {cname} bash -lc "
                f"\"/usr/local/bin/dash-client -y -hostname {self.server_ip} -scheme {scheme}\""
            )
            print(f"[DIAG] {cname}: dash-client -> {out_host}")
            subprocess.run(run_cmd, shell=True, check=False)

            # grab and move the newest file created by the server
            newest = None
            files = list(default_dir.glob("*.json.gz"))
            if files:
                newest = max(files, key=lambda p: p.stat().st_mtime)

            if newest:
                newest.rename(out_host)
            else:
                print(f"[WARNING] No output found for {cname} in {default_dir}")

        print("[DIAG] Round finished.\n")


    # Brief: Executes the full topology setup
    def run(self, 
            run_tests: bool = False, 
            skip_discovery: bool = False, 
            run_qos_diagnostics: bool = False
            ):
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

        if run_tests:
            self._run_tests()
        else:
            print("[INFO] Tests skipped. To run them, set 'run_tests=True' or use the interaction.")

        if run_qos_diagnostics:
            self._run_qos_diagnostics()
        else:
            print("[INFO] QoS diagnostics skipped.")

