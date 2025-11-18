import subprocess
import time
import sys
import random
from dash_server import DashServer
from dash_client import DashClient
from switch_modified import Switch
from onos import ONOS


# ========================= (Topology Constants and Default Configuration) ======================== #

POPS = [
    "PoP-AC", "PoP-AL", "PoP-AM", "PoP-AP", "PoP-BA", "PoP-CE",
    "PoP-DF", "PoP-ES", "PoP-GO", "PoP-MA", "PoP-MG", "PoP-MS", "PoP-MT", "PoP-PA",
    "PoP-PB", "PoP-PE", "PoP-PI", "PoP-PR", "PoP-RJ", "PoP-RN", "PoP-RO", "PoP-RR",
    "PoP-RS", "PoP-SC", "PoP-SE", "PoP-SP", "PoP-TO"
]

# Adjacency Matrix representing the PoP connectivity
ADJACENCY_MATRIX = [
    # AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO
    [ 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0 ],  # PoP-AC
    [ 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0 ],  # PoP-AL
    [ 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0 ],  # PoP-AM
    [ 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 ],  # PoP-AP
    [ 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0 ],  # PoP-BA
    [ 0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1 ],  # PoP-CE
    [ 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0 ],  # PoP-DF
    [ 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 ],  # PoP-ES
    [ 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 ],  # PoP-GO
    [ 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0 ],  # PoP-MA
    [ 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 ],  # PoP-MG
    [ 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1 ],  # PoP-MS
    [ 0, 0, 1, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 ],  # PoP-MT
    [ 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0 ],  # PoP-PA
    [ 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 ],  # PoP-PB
    [ 0, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 ],  # PoP-PE
    [ 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 1, 0 ],  # PoP-PI
    [ 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0 ],  # PoP-PR
    [ 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 ],  # PoP-RJ
    [ 1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 ],  # PoP-RN
    [ 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 ],  # PoP-RO
    [ 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0 ],  # PoP-RR
    [ 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 1, 0 ],  # PoP-RS
    [ 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 ],  # PoP-SC
    [ 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 1, 0, 0, 0 ],  # PoP-SE
    [ 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 ],  # PoP-SP
    [ 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 ]   # PoP-TO
]

DEFAULT_CONFIG = {
    "hosts_per_pop": 1,          # Default number of clients per PoP
    "server_pop": "PoP-RS",      # Default PoP where the DASH server is attached
    "server_ip": "192.168.0.1",  # Default IP address for the DASH server
    "client_ip_start": 2,        # Starting octet for client IPs (192.168.0.X)
    "randomize_link_properties": False, # Whether link properties should be randomized or not            
    "THROUGHPUT": "10mbit",             # TC Throughput (mbits) for each if
    "DELAY": "20ms",                    # TC Delay (ms) for each if 
    "JITTER": "5ms"                     # TC Jitter (ms) for each if
}

# Range of values for simulating realistic links if randomize_link_properties is true
RANDOM_RANGES = {
    "THROUGHPUT": list(range(5, 31)),
    "DELAY": list(range(50, 201)),
    "JITTER": list(range(5, 21))
}

# ========================= (Utility Functions) ======================== #

# Brief: Collects custom configuration values from the user, allowing to change the default topology and link properties (QoS)
def get_custom_config(default_config: dict) -> dict:
    custom_config = default_config.copy()
    print("\n--- Interactive Topology Configuration ---")

    try:
        # Get the desired number of hosts per Point of Presence (PoP)
        hosts = input(f"Hosts per PoP (Default: {default_config['hosts_per_pop']}): ").strip()
        if hosts:
            custom_config['hosts_per_pop'] = int(hosts)
    except ValueError:
        print("[WARNING] Invalid value for hosts. Using default.")

    # Ask whether link QoS properties should be randomized
    ans_random = input(f"Randomize QoS properties? (Default: {'Y' if default_config['randomize_link_properties'] else 'N'}) [y/N]: ").strip().lower()
    custom_config['randomize_link_properties'] = ans_random == 'y'

    # If randomization is NOT enabled, prompt for fixed QoS values.
    if not custom_config['randomize_link_properties']:
        print("\n--- Fixed QoS Values ---")
        
        # Rate Capacity (Throughput limit using TC)
        rate = input(f"Fixed Rate Capacity (e.g., 10mbit) (Default: {default_config['THROUGHPUT']}): ").strip()
        if rate:
            custom_config['THROUGHPUT'] = rate.lower()

        # Delay
        delay = input(f"Fixed Delay (e.g., 20ms) (Default: {default_config['DELAY']}): ").strip()
        if delay:
            custom_config['DELAY'] = delay.lower()
            
        # Jitter
        jitter = input(f"Fixed Jitter Variance (e.g., 5ms) (Default: {default_config['JITTER']}): ").strip()
        if jitter:
            custom_config['JITTER'] = jitter.lower()
            
    return custom_config

# Brief: Retrieves the IP address of a Docker container by its name
def get_container_ip(name: str) -> str:
    cmd = f"docker inspect -f '{{{{range .NetworkSettings.Networks}}}}{{{{.IPAddress}}}}{{{{end}}}}' {name}"
    return subprocess.check_output(cmd, shell=True, text=True).strip()

# Brief: Stops and removes all Docker containers and purges unused networks
def cleanup() -> None:
    print("\n[CLEANUP] Removing old SSH key for ONOS...")
    subprocess.run('ssh-keygen -R "[172.17.0.2]:8101" >/dev/null 2>&1', shell=True)
    print("[CLEANUP] Stopping and removing all Docker containers...")
    subprocess.run('sudo docker rm -f $(sudo docker ps -aq) >/dev/null 2>&1 || true', shell=True)
    print("[CLEANUP] Removing unused Docker networks...")
    subprocess.run('sudo docker network prune -f >/dev/null 2>&1', shell=True)
    print("[CLEANUP] Done.")


# Brief: Displays a countdown timer and pauses execution
def sleep_countdown(t=10) -> None:
    for i in range(t, 0, -1):
        print(f"  {i} seconds remaining ...", end="\r")
        time.sleep(1)
    print("                           ") # Clears the line

# Brief: Prints a simple ASCII art banner for the experiment
def print_banner() -> None:
    art = r"""

      .oooooo.   oooooooooo.   ooooo     ooo 
     d8P'  `Y8b  `888'   `Y8b  `888b.     `8' 
    888           888      888  8 `88b.    8  
    888           888      888  8   `88b.  8  
    888           888      888  8     `88b.8  
    `88b    ooo   888     d88'  8       `888  
     `Y8bood8P'  o888bood8P'   o8o        `8  

    ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
    
             DASH TOPOLOGY EXPERIMENT
    """
    print(art)


# ========================= (Topology Class) ======================== #

class DashTopology:
    """
    Brief: Encapsulates all the logic to build, configure and test the topology
    """
    def __init__(self, config: dict = DEFAULT_CONFIG):
        
        # Merge user configuration with defaults
        self.config = DEFAULT_CONFIG.copy()
        self.config.update(config)

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
    def setup_controller(self):
        print("\n[Experiment] ... Creating ONOS controller")
        c1 = ONOS("c1")
        c1.instantiate(mapPorts=True)
        self.onos_ip = get_container_ip("c1")
        print(f"[CTRL] ONOS IP: {self.onos_ip}")
        print("Waiting for ONOS to initialize (30s) ...")
        sleep_countdown(30)
        print("[CTRL] Activating OpenFlow + Host Provider + Reactive Forwarding")
        c1.activateONOSApps(self.onos_ip)
        print("[OK] ONOS is ready!\n")


    # Brief: Creates all OVS switches and connects them to the ONOS controller
    def setup_switches(self):
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
    def connect_switches(self):
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
    def setup_hosts(self):
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
                    throughput = f"{random.choice(RANDOM_RANGES['THROUGHPUT'])}mbit"
                    delay = f"{random.choice(RANDOM_RANGES['DELAY'])}ms"
                    jitter = f"{random.choice(RANDOM_RANGES['JITTER'])}ms"
                else:
                    throughput = self.config["THROUGHPUT"]
                    delay = self.config["DELAY"]
                    jitter = self.config["JITTER"]

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
    def run_discovery(self):
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
        sleep_countdown(3)
        print("[OK] Hosts should be visible in ONOS.\n")


    # Brief: Executes basic connectivity tests (ping/curl) from the first client to the server
    def run_tests(self):
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
    def run_qos_diagnostics(self, max_clients: int = 3):
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


    # Brief: Executes the full topology setup
    def run(self, run_tests: bool = False, skip_discovery: bool = False, run_qos_diagnostics: bool = False):
        print_banner()
        
        self.setup_controller()
        self.setup_switches()
        self.connect_switches()
        self.setup_hosts()
        
        print("Waiting for network stabilization (5s)...\n")
        sleep_countdown(5)
        
        if not skip_discovery:
            self.run_discovery()
        else:
            print("[INFO] Host discovery (ping-all) skipped.")

        if run_tests:
            self.run_tests()
        else:
            print("[INFO] Tests skipped. To run them, set 'run_tests=True' or use the interaction.")

        if run_qos_diagnostics:
            self.run_qos_diagnostics()
        else:
            print("[INFO] QoS diagnostics skipped.")


if __name__ == "__main__":
    cleanup()

    RUN_TESTS_DEFAULT = False 
    SKIP_DISCOVERY_DEFAULT = False 

    try:
        ans_custom = input("Do you want to configure the topology interactively (Hosts, QoS, etc.)? [y/N] ").strip().lower()        
        if ans_custom == 'y':
            # Collect input and create a custom configuration dictionary
            final_config = get_custom_config(DEFAULT_CONFIG)
        else:
            final_config = DEFAULT_CONFIG

        topology = DashTopology(config=final_config)
        
        # Interactive mode for discovery and tests
        run_tests = RUN_TESTS_DEFAULT
        skip_discovery = SKIP_DISCOVERY_DEFAULT

        # Overwrite defaults if running interactively
        ans_discover = input("Do you want the controller to discover all hosts? [y/N] ").strip().lower()
        skip_discovery = ans_discover != "y"
        
        ans_test = input("Run quick tests (ping/curl)? [y/N] ").strip().lower()
        run_tests = ans_test == "y"
        
        run_qos_diagnostics = input("Run QoS diagnostics (tc qdisc + ping RTT)? [y/N] ").strip().lower()
        run_qos_diagnostics = run_qos_diagnostics == "y"

        topology.run(run_tests=run_tests, skip_discovery=skip_discovery, run_qos_diagnostics=run_qos_diagnostics)

    except KeyboardInterrupt:
        print("\n[INFO] Execution interrupted by user. Stopping.")
        sys.exit(0)
    except Exception as e:
        print(f"\n[FATAL ERROR] An unexpected error occurred: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        print("\n[INFO] Attempting to run cleanup before exiting...")
        cleanup()
        sys.exit(1)
        
