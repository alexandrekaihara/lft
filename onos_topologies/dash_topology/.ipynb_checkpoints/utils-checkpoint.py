import subprocess
import time
import os
import json
import time
import csv
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

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

    # If randomization is NOT enabled, prompt for fixed QoS values
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


# Brief: Serializes a dictionary to a JSON file, creating parent directories
def write_json(p: Path, obj: dict):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


# Brief: Validates repetition outputs by checking if all clients generated data files
# Marks as invalid if any client output is missing
# Expects `topology.clients` to be a dict with client container names
def validate_rep_outputs(rep_dir: Path, topology: Any):
    iter_dir = rep_dir / "iter_0000" / "clients"
    missing = []
    for cname in topology.clients.keys():
        fp = iter_dir / f"{cname}.json.gz"
        if not fp.exists() or fp.stat().st_size == 0:
            missing.append(cname)
    return missing


# Brief: Copies current DashLinkSniffer ring buffer PCAPs to the repetition directory for versioning
# Copies files from $LFT_DATADIR/pcaps to rep_dir to snapshot 'before'/'after' states
# and avoids depending on container existence after cleanup.
def snapshot_sniffer_ring(rep_dir: Path, tag: str):
    lft_datadir = os.environ.get("LFT_DATADIR")
    if not lft_datadir:
        raise RuntimeError("LFT_DATADIR is not defined in the environment.")

    src = Path(lft_datadir) / "pcaps"
    dst = rep_dir / f"pcaps_{tag}"
    dst.mkdir(parents=True, exist_ok=True)

    if not src.exists():
        (dst / "EMPTY").write_text("no $LFT_DATADIR/pcaps found", encoding="utf-8")
        return

    files = sorted(src.glob("*"), key=lambda p: p.stat().st_mtime if p.exists() else 0)

    copied = 0
    for p in files:
        if p.is_file():
            shutil.copy2(p, dst / p.name)
            copied += 1

    (dst / "SNAPSHOT.txt").write_text(
        f"snapshot_tag={tag}\n"
        f"when_utc={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n"
        f"files={copied}\n",
        encoding="utf-8",
    )


def _run(cmd: List[str]) -> Tuple[int, str, str]:
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, p.stdout or "", p.stderr or ""


def snapshot_ovs_state(
    switch_names: List[str],
    outdir: Path,
    of_version: str = "OpenFlow13",
    parse_csv: bool = True,
    max_workers: int = 8,
) -> None:
    """
    Snapshot OVS/OpenFlow state from all switches and write raw + parsed outputs.

    Files written per switch:
      - dump-flows.txt (+ flows.csv if parse_csv=True)
      - dump-ports.txt (+ ports.csv if parse_csv=True)
      - show.txt

    Note: This is not truly atomic, but it is executed as close as possible in time by
    running switch snapshots concurrently (one worker per switch).
    """
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    def snap_one(sw: str) -> None:
        sw_dir = outdir / sw
        sw_dir.mkdir(parents=True, exist_ok=True)

        # Raw outputs
        rc, out, err = _run(["docker", "exec", sw, "ovs-ofctl", "-O", of_version, "dump-flows", sw])
        (sw_dir / "dump-flows.txt").write_text(out + ("\n" + err if err else ""), encoding="utf-8")

        rc, out, err = _run(["docker", "exec", sw, "ovs-ofctl", "-O", of_version, "dump-ports", sw])
        (sw_dir / "dump-ports.txt").write_text(out + ("\n" + err if err else ""), encoding="utf-8")

        rc, out, err = _run(["docker", "exec", sw, "ovs-ofctl", "-O", of_version, "show", sw])
        (sw_dir / "show.txt").write_text(out + ("\n" + err if err else ""), encoding="utf-8")

        # Parsed outputs (CSV)
        if parse_csv:
            flows_txt = (sw_dir / "dump-flows.txt").read_text(encoding="utf-8", errors="ignore")
            ports_txt = (sw_dir / "dump-ports.txt").read_text(encoding="utf-8", errors="ignore")
            _write_flows_csv(flows_txt, sw_dir / "flows.csv", switch_name=sw)
            _write_ports_csv(ports_txt, sw_dir / "ports.csv", switch_name=sw)

    with ThreadPoolExecutor(max_workers=min(max_workers, max(1, len(switch_names)))) as ex:
        futs = [ex.submit(snap_one, sw) for sw in switch_names]
        for f in as_completed(futs):
            f.result()


# Brief: Parse ovs-ofctl dump-flows output into a CSV suitable for Pandas
def _write_flows_csv(dump_flows_text: str, out_csv: Path, switch_name: str) -> None:
    rows: List[Dict[str, str]] = []

    for line in dump_flows_text.splitlines():
        line = line.strip()
        if not line or line.startswith("OFPST_FLOW") or line.startswith("NXST_FLOW"):
            continue
        if "actions=" not in line:
            continue

        flow_raw = line
        left, actions_part = line.split("actions=", 1)
        actions_raw = actions_part.strip()

        cookie = _rx(left, r"cookie=([^, ]+)")
        duration_s = _rx(left, r"duration=([0-9.]+)s")
        table = _rx(left, r"table=([0-9]+)")
        n_packets = _rx(left, r"n_packets=([0-9]+)")
        n_bytes = _rx(left, r"n_bytes=([0-9]+)")
        priority = _rx(left, r"priority=([0-9]+)")

        # Match is everything after priority=... up to actions= (kept raw, comma-separated)
        match_raw = ""
        if "priority=" in left:
            m = re.search(r"priority=[0-9]+,(.*)$", left)
            if m:
                match_raw = m.group(1).strip().rstrip(",")
        else:
            match_raw = left.strip().rstrip(",")

        rows.append(
            {
                "switch": switch_name,
                "cookie": cookie,
                "table": table,
                "priority": priority,
                "duration_s": duration_s,
                "n_packets": n_packets,
                "n_bytes": n_bytes,
                "match_raw": match_raw,
                "actions_raw": actions_raw,
                "flow_raw": flow_raw,
            }
        )

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "switch",
                "cookie",
                "table",
                "priority",
                "duration_s",
                "n_packets",
                "n_bytes",
                "match_raw",
                "actions_raw",
                "flow_raw",
            ],
        )
        w.writeheader()
        w.writerows(rows)


# Brief: Parse ovs-ofctl dump-ports output into CSV (rx/tx pkts/bytes/drop/errs)
def _write_ports_csv(dump_ports_text: str, out_csv: Path, switch_name: str) -> None:
    rows: List[Dict[str, str]] = []

    # Typical format:
    #  port 1: rx pkts=..., bytes=..., drop=..., errs=..., ...
    #          tx pkts=..., bytes=..., drop=..., errs=..., ...
    current = None

    port_re = re.compile(r"^\s*port\s+(\d+):\s*(.*)$")
    rx_re = re.compile(r"rx\s+pkts=(\d+),\s*bytes=(\d+),\s*drop=(\d+),\s*errs=(\d+)")
    tx_re = re.compile(r"tx\s+pkts=(\d+),\s*bytes=(\d+),\s*drop=(\d+),\s*errs=(\d+)")

    for line in dump_ports_text.splitlines():
        m = port_re.match(line)
        if m:
            # Flush previous port
            if current:
                rows.append(current)
            port_no = m.group(1)
            current = {
                "switch": switch_name,
                "port_no": port_no,
                "rx_pkts": "",
                "rx_bytes": "",
                "rx_drop": "",
                "rx_errs": "",
                "tx_pkts": "",
                "tx_bytes": "",
                "tx_drop": "",
                "tx_errs": "",
            }
            # Parse rx inline if present
            mrx = rx_re.search(m.group(2))
            if mrx:
                current.update(
                    {
                        "rx_pkts": mrx.group(1),
                        "rx_bytes": mrx.group(2),
                        "rx_drop": mrx.group(3),
                        "rx_errs": mrx.group(4),
                    }
                )
            continue

        if current:
            mrx = rx_re.search(line)
            if mrx:
                current.update(
                    {
                        "rx_pkts": mrx.group(1),
                        "rx_bytes": mrx.group(2),
                        "rx_drop": mrx.group(3),
                        "rx_errs": mrx.group(4),
                    }
                )
            mtx = tx_re.search(line)
            if mtx:
                current.update(
                    {
                        "tx_pkts": mtx.group(1),
                        "tx_bytes": mtx.group(2),
                        "tx_drop": mtx.group(3),
                        "tx_errs": mtx.group(4),
                    }
                )

    if current:
        rows.append(current)

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "switch",
                "port_no",
                "rx_pkts",
                "rx_bytes",
                "rx_drop",
                "rx_errs",
                "tx_pkts",
                "tx_bytes",
                "tx_drop",
                "tx_errs",
            ],
        )
        w.writeheader()
        w.writerows(rows)


def _rx(text: str, pattern: str) -> str:
    m = re.search(pattern, text)
    return m.group(1) if m else ""
