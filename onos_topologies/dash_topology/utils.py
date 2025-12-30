import subprocess
import time
import time
import csv
import re
import io
import shutil
import gzip
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

PCAP_FIELDS: List[str] = [
    "frame.time_epoch",
    "frame.len",
    "ip.src",
    "ip.dst",
    "ipv6.src",
    "ipv6.dst",
    "_ws.col.Protocol",
    "tcp.srcport",
    "tcp.dstport",
    "tcp.flags",
    "tcp.stream",
    "icmp.type",
    "icmp.code",
    "icmpv6.type",
    "icmpv6.code",
]

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


def _parse_snapshot_iface_from_name(pcap_path: Path) -> Tuple[Optional[int], str]:
    """
    Expected parsing:
      - "3%eth0"          -> snapshot_idx=3, interface="eth0"
      - "snapshot_3%eth0" -> snapshot_idx=3, interface="eth0"
    """
    stem = pcap_path.stem  # no ".pcap"
    if "%" not in stem:
        return None, ""

    left, iface = stem.split("%", 1)
    m = re.search(r"(\d+)", left)
    snap = int(m.group(1)) if m else None
    return snap, iface


def _tshark_cmd(pcap_path: Path, display_filter: Optional[str]) -> List[str]:
    cmd = ["tshark", "-r", str(pcap_path)]
    if display_filter:
        cmd += ["-Y", display_filter]

    cmd += [
        "-T", "fields",
        "-E", "header=y",
        "-E", "separator=,",
        "-E", "quote=d",
        "-E", "occurrence=f",
    ]
    for f in PCAP_FIELDS:
        cmd += ["-e", f]
    return cmd


# Brief: Convert ALL *.pcap in `tcpdump_dir` into ONE CSV at `out_csv`.
#  Adds columns: snapshot_idx, interface (parsed from filename split by '%').
#  Returns stats dict: {"pcaps": X, "rows": Y}
def snapshot_pcaps_to_single_csv(
    tcpdump_dir: Path,
    out_csv: Path,
    display_filter: Optional[str] = None,
    delete_pcaps: bool = False,
) -> Dict[str, int]:
    tcpdump_dir = Path(tcpdump_dir)
    out_csv = Path(out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    pcaps = sorted(tcpdump_dir.glob("*.pcap"))
    total_rows = 0

    out_fields = ["snapshot_idx", "interface"] + PCAP_FIELDS

    with out_csv.open("w", newline="", encoding="utf-8") as f_out:
        w = csv.DictWriter(f_out, fieldnames=out_fields)
        w.writeheader()

        for pcap in pcaps:
            snap_idx, iface = _parse_snapshot_iface_from_name(pcap)

            # If parsing failed, still keep something
            snap_val = snap_idx if snap_idx is not None else ""

            cmd = _tshark_cmd(pcap, display_filter)
            proc = subprocess.run(cmd, capture_output=True, text=True)

            # only rely on stdout
            if not proc.stdout.strip():
                if delete_pcaps:
                    try:
                        pcap.unlink(missing_ok=True)
                    except Exception:
                        pass
                continue

            reader = csv.DictReader(io.StringIO(proc.stdout))
            for row in reader:
                out_row: Dict[str, str] = {
                    "snapshot_idx": str(snap_val),
                    "interface": iface,
                }
                for k in PCAP_FIELDS:
                    out_row[k] = row.get(k, "") if row else ""
                w.writerow(out_row)
                total_rows += 1

            if delete_pcaps:
                try:
                    pcap.unlink(missing_ok=True)
                except Exception:
                    pass

    return {"pcaps": len(pcaps), "rows": total_rows}


def _extract_snapshot_number_from_path(p: Path) -> int:
    # Expected: .../snapshots/snapshot_12/tcpdump/packet_flow.csv
    m = re.search(r"snapshot_(\d+)", str(p))
    return int(m.group(1)) if m else 10**9


# Brief: Merge all per-snapshot packet_flow.csv into a single CSV at run_root/out_csv_name.
#  Returns stats dict:
#   - files: number of input CSVs found
#   - rows: total rows written (excluding header)
def merge_all_snapshot_csvs(
    run_root: Path,
    out_csv_name: str = "packet_flow_all.csv",
    glob_pattern: str = "snapshots/snapshot_*/tcpdump/packet_flow.csv",
    delete_inputs: bool = False,
) -> Dict[str, int]:
    run_root = Path(run_root)
    out_csv = run_root / out_csv_name

    inputs: List[Path] = sorted(
        run_root.glob(glob_pattern),
        key=_extract_snapshot_number_from_path,
    )

    if not inputs:
        return {"files": 0, "rows": 0}

    total_rows = 0
    expected_fields: Optional[List[str]] = None

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f_out:
        writer: Optional[csv.DictWriter] = None

        for in_path in inputs:
            with in_path.open("r", newline="", encoding="utf-8") as f_in:
                reader = csv.DictReader(f_in)
                if reader.fieldnames is None:
                    continue  # empty file

                # initialize schema from the first file
                if expected_fields is None:
                    expected_fields = list(reader.fieldnames)
                    writer = csv.DictWriter(f_out, fieldnames=expected_fields)
                    writer.writeheader()

                # if schema differs, fail fast
                if list(reader.fieldnames) != expected_fields:
                    raise ValueError(
                        f"Schema mismatch in {in_path}. "
                        f"Expected {expected_fields}, got {reader.fieldnames}"
                    )

                # append rows
                assert writer is not None
                for row in reader:
                    # skip completely empty rows if any
                    if not row or all((v is None or str(v).strip() == "") for v in row.values()):
                        continue
                    writer.writerow(row)
                    total_rows += 1

            if delete_inputs:
                try:
                    in_path.unlink(missing_ok=True)
                except Exception:
                    pass

    return {"files": len(inputs), "rows": total_rows}
