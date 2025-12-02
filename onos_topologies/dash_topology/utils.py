import subprocess
import time
import time
import csv
import re
import shutil
from pathlib import Path
from typing import Dict, List, Tuple, Optional
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


# Brief: Simply runs a command using the subprocess module and saves the stdout and stderr content
def _run(cmd: List[str]) -> Tuple[int, str, str]:
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, p.stdout or "", p.stderr or ""


# Brief: Snapshot OVS/OpenFlow state from all switches and write raw + parsed outputs
# Files written per switch:
#   - dump-flows.txt (+ flows.csv if parse_csv=True)
#   - dump-ports.txt (+ ports.csv if parse_csv=True)
#   - show.txt
def snapshot_ovs_state(
    switch_names: List[str],
    outdir: Path,
    of_version: str = "OpenFlow13",
    parse_csv: bool = True,
    max_workers: int = 8,
) -> None:
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

# Brief: Extracts the first capture group from a regex search
def _rx(text: str, pattern: str) -> str:
    m = re.search(pattern, text)
    return m.group(1) if m else ""


# Brief: Appends a line to events.log under the given directory
def append_event(rep_dir: Path, line: str) -> None:
    rep_dir.mkdir(parents=True, exist_ok=True)
    with (rep_dir / "events.log").open("a", encoding="utf-8") as f:
        f.write(line.rstrip() + "\n")


# Brief: convert a PCAP to a CSV using tshark (host-side)
def pcap_to_csv(pcap_path: Path, csv_path: Path, display_filter: Optional[str] = None) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = ["tshark", "-r", str(pcap_path)]

    # Only add -Y if a filter is provided
    if display_filter:
        cmd += ["-Y", display_filter]

    cmd += [
        "-T", "fields",
        "-E", "header=y",
        "-E", "separator=,",
        "-E", "quote=d",
        "-E", "occurrence=f",
        "-e", "frame.time_epoch",
        "-e", "frame.len",
        "-e", "ip.src",
        "-e", "ip.dst",
        "-e", "ipv6.src",
        "-e", "ipv6.dst",
        "-e", "_ws.col.Protocol",
        "-e", "tcp.srcport",
        "-e", "tcp.dstport",
        "-e", "tcp.flags",
        "-e", "tcp.stream",
        "-e", "icmp.type",
        "-e", "icmp.code",
        "-e", "icmpv6.type",
        "-e", "icmpv6.code",
    ]

    with open(csv_path, "w", encoding="utf-8") as f:
        subprocess.run(cmd, stdout=f, stderr=subprocess.DEVNULL, check=False)


def move_closed_pcaps(live_root: Path, pcaps_dir: Path, clean_live: bool = True) -> int:
    moved = 0

    for sw_dir in live_root.glob("*"):
        if not sw_dir.is_dir():
            continue
        swname = sw_dir.name

        for iface_dir in sw_dir.glob("*"):
            if not iface_dir.is_dir():
                continue
            ifname = iface_dir.name

            pcaps = sorted(iface_dir.glob("dump_*.pcap*"), key=lambda p: p.stat().st_mtime)
            if len(pcaps) < 2:
                continue

            for p in pcaps[:-1]:  # skip newest
                dst = pcaps_dir / swname / ifname / p.name
                dst.parent.mkdir(parents=True, exist_ok=True)

                if dst.exists():
                    if clean_live:
                        try:
                            p.unlink(missing_ok=True)
                        except Exception:
                            pass
                    continue

                if clean_live:
                    try:
                        shutil.move(str(p), str(dst))
                    except Exception:
                        dst.write_bytes(p.read_bytes())
                        try:
                            p.unlink(missing_ok=True)
                        except Exception:
                            pass
                else:
                    dst.write_bytes(p.read_bytes())

                moved += 1

    return moved
