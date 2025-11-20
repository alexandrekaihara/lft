import subprocess
import time

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
    print("                           ") # clears the line


# Brief: Prints an art banner for the experiment
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


# Brief: Allows for custom topology configuration
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
        rate = input(f"Fixed Rate Capacity (e.g., 10mbit) (Default: {default_config['throughput']}): ").strip()
        if rate:
            custom_config['throughput'] = rate.lower()
        # Delay
        delay = input(f"Fixed Delay (e.g., 20ms) (Default: {default_config['delay']}): ").strip()
        if delay:
            custom_config['delay'] = delay.lower()
        # Jitter
        jitter = input(f"Fixed Jitter Variance (e.g., 5ms) (Default: {default_config['jitter']}): ").strip()
        if jitter:
            custom_config['jitter'] = jitter.lower()
    return custom_config
