import subprocess
import time
import time
import csv
import re
import io
import json
import threading
import requests
from datetime import datetime, timezone, timedelta
from requests.auth import HTTPBasicAuth
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional, Iterable
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
    max_workers: int = 8,
    snapshot_idx: Optional[int] = None,
    parse_csv: bool = True,  # keeps compatibility with your caller
) -> None:
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    flows_out = outdir / "ovs_flows.csv"
    ports_out = outdir / "ovs_ports.csv"

    flows_lock = threading.Lock()
    ports_lock = threading.Lock()

    snap_val = "" if snapshot_idx is None else str(snapshot_idx)

    with flows_out.open("w", newline="", encoding="utf-8") as flows_f, ports_out.open("w", newline="", encoding="utf-8") as ports_f:
        flows_writer = csv.DictWriter(flows_f, fieldnames=OVS_FLOWS_FIELDS, extrasaction="ignore")
        ports_writer = csv.DictWriter(ports_f, fieldnames=OVS_PORTS_FIELDS, extrasaction="ignore")

        if parse_csv:
            flows_writer.writeheader()
            ports_writer.writeheader()

        def snap_one(sw: str) -> None:
            rc, flows_txt, err = _run(["docker", "exec", sw, "ovs-ofctl", "-O", of_version, "dump-flows", sw])
            if err:
                flows_txt += "\n" + err

            rc, ports_txt, err = _run(["docker", "exec", sw, "ovs-ofctl", "-O", of_version, "dump-ports", sw])
            if err:
                ports_txt += "\n" + err

            if not parse_csv:
                return

            # Write flows
            with flows_lock:
                for row in _iter_flows_rows(flows_txt):
                    out_row = {"snapshot": snap_val, "switch": sw, **row}
                    flows_writer.writerow(out_row)

            # Write ports
            with ports_lock:
                for row in _iter_ports_rows(ports_txt):
                    out_row = {"snapshot": snap_val, "switch": sw, **row}
                    ports_writer.writerow(out_row)

        with ThreadPoolExecutor(max_workers=min(max_workers, max(1, len(switch_names)))) as ex:
            futs = [ex.submit(snap_one, sw) for sw in switch_names]
            for f in as_completed(futs):
                f.result()


# Brief: sends flow rule to ONOS via REST.
def push_onos_flow(onos_ip, device_id, criteria, out_port, priority=60000, app_id="org.onosproject.rtt_measure"):
    url = f"http://{onos_ip}:8181/onos/v1/flows/{device_id}?appId={app_id}"

    payload = {
        "priority": priority,
        "isPermanent": True,
        "selector": {"criteria": criteria},
        "treatment": {"instructions": [{"type": "OUTPUT", "port": str(out_port)}]},
    }

    try:
        res = requests.post(url, json=payload, auth=HTTPBasicAuth("onos", "rocks"), timeout=3)
        return res.status_code in (200, 201)
    except Exception as e:
        print(f"Error pushing flow to ONOS: {e}")
        return False


def merge_all_snapshot_ovs_csvs(
    run_root: Path,
    delete_inputs: bool = False,
) -> Dict[str, Any]:
    run_root = Path(run_root)
    snaps_root = run_root / "snapshots"

    out_flows = run_root / "ovs_flows_all.csv"
    out_ports = run_root / "ovs_ports_all.csv"

    stats_flows = _merge_many_csvs(
        in_paths=sorted(snaps_root.glob("snapshot_*/ovs/ovs_flows.csv")),
        out_csv=out_flows,
        delete_inputs=delete_inputs,
    )
    stats_ports = _merge_many_csvs(
        in_paths=sorted(snaps_root.glob("snapshot_*/ovs/ovs_ports.csv")),
        out_csv=out_ports,
        delete_inputs=delete_inputs,
    )

    return {
        "flows": stats_flows,
        "ports": stats_ports,
    }


def _merge_many_csvs(in_paths, out_csv: Path, delete_inputs: bool) -> Dict[str, Any]:
    import csv

    in_paths = [Path(p) for p in in_paths if Path(p).exists()]
    if not in_paths:
        return {"files": 0, "rows": 0, "out": str(out_csv)}

    rows_written = 0
    files_used = 0

    with in_paths[0].open("r", newline="", encoding="utf-8") as f0:
        r0 = csv.DictReader(f0)
        fieldnames = list(r0.fieldnames or [])

    with out_csv.open("w", newline="", encoding="utf-8") as fo:
        w = csv.DictWriter(fo, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()

        for p in in_paths:
            files_used += 1
            with p.open("r", newline="", encoding="utf-8") as fi:
                reader = csv.DictReader(fi)
                for row in reader:
                    w.writerow(row)
                    rows_written += 1
            if delete_inputs:
                try:
                    p.unlink()
                except FileNotFoundError:
                    pass

    return {"files": files_used, "rows": rows_written, "out": str(out_csv)}


# Brief: Extracts the first capture group from a regex search
def _rx(text: str, pattern: str) -> str:
    m = re.search(pattern, text)
    return m.group(1) if m else ""


OVS_FLOWS_FIELDS: List[str] = [
    "snapshot",
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
]

OVS_PORTS_FIELDS: List[str] = [
    "snapshot",
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
]


# Brief: Parses ovs-ofctl dump-flows output and yields one dict per flow line.
def _iter_flows_rows(dump_flows_text: str) -> Iterable[Dict[str, str]]:
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

        if "priority=" in left:
            m = re.search(r"priority=[0-9]+,(.*)$", left)
            match_raw = m.group(1).strip().rstrip(",") if m else ""
        else:
            match_raw = left.strip().rstrip(",")

        yield {
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


# Brief: Parses ovs-ofctl dump-ports output and yields one dict per port
def _iter_ports_rows(dump_ports_text: str) -> Iterable[Dict[str, str]]:
    port_re = re.compile(r"^\s*port\s+(\d+):\s*(.*)$")
    rx_re = re.compile(r"rx\s+pkts=(\d+),\s*bytes=(\d+),\s*drop=(\d+),\s*errs=(\d+)")
    tx_re = re.compile(r"tx\s+pkts=(\d+),\s*bytes=(\d+),\s*drop=(\d+),\s*errs=(\d+)")

    current: Optional[Dict[str, str]] = None

    for line in dump_ports_text.splitlines():
        m = port_re.match(line)
        if m:
            if current:
                yield current

            port_no = m.group(1)
            current = {
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

            # Parse rx inline
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
        yield current


# Brief: Appends a line to events.log under the given directory
def append_event(rep_dir: Path, line: str) -> None:
    rep_dir.mkdir(parents=True, exist_ok=True)
    with (rep_dir / "events.log").open("a", encoding="utf-8") as f:
        f.write(line.rstrip() + "\n")


# Brief: Expected parsing:
# - "3%eth0"          -> snapshot_idx=3, interface="eth0"
# - "snapshot_3%eth0" -> snapshot_idx=3, interface="eth0"
def _parse_snapshot_iface_from_name(pcap_path: Path) -> Tuple[Optional[int], str]:
    stem = pcap_path.stem  # no ".pcap"
    if "%" not in stem:
        return None, ""

    left, iface = stem.split("%", 1)
    m = re.search(r"(\d+)", left)
    snap = int(m.group(1)) if m else None
    return snap, iface

# Obs: Display Filter é um filtro de protocolo PÓS-CAPTURA. O BPF filter do tcpdump filtra em tempo de execução!!
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


HW_FIELDS = [
    "snapshot_idx",
    "ts_epoch",
    "cpu_pct",
    "ram_used_bytes",
    "disk_read_bytes",
    "disk_write_bytes",
]

_DISK_RE = re.compile(r"^(sd[a-z]+\d*|vd[a-z]+\d*|nvme\d+n\d+p?\d*)$")


def _cpu_stat() -> Tuple[int, int]:
    with open("/proc/stat", "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.startswith("cpu "):
                v = [int(x) for x in line.split()[1:]]
                idle = (v[3] if len(v) > 3 else 0) + (v[4] if len(v) > 4 else 0)
                total = sum(v[:8]) if len(v) >= 8 else sum(v)
                return idle, total
    return 0, 0


def _ram_used_bytes() -> int:
    mem_total = 0
    mem_avail = 0
    with open("/proc/meminfo", "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.startswith("MemTotal:"):
                mem_total = int(line.split()[1]) * 1024
            elif line.startswith("MemAvailable:"):
                mem_avail = int(line.split()[1]) * 1024
    return max(0, mem_total - mem_avail)


def _disk_rw_bytes() -> Tuple[int, int]:
    r_sec = 0
    w_sec = 0
    with open("/proc/diskstats", "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            p = line.split()
            if len(p) < 14:
                continue
            name = p[2]
            if not _DISK_RE.match(name):
                continue
            r_sec += int(p[5])
            w_sec += int(p[9])
    return r_sec * 512, w_sec * 512


def hw_state() -> Tuple[int, int, int, int]:
    idle, total = _cpu_stat()
    dr, dw = _disk_rw_bytes()
    return idle, total, dr, dw


def hw_sample(csv_path: Path, snapshot_idx: int, state: List[int]) -> None:
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    idle0, total0, dr0, dw0 = state
    idle1, total1 = _cpu_stat()
    dr1, dw1 = _disk_rw_bytes()

    idle_d = max(0, idle1 - idle0)
    total_d = max(0, total1 - total0)
    cpu_pct = (100.0 * (1.0 - (idle_d / total_d))) if total_d > 0 else 0.0

    row = {
        "snapshot_idx": str(snapshot_idx),
        "ts_epoch": str(time.time()),
        "cpu_pct": f"{cpu_pct:.3f}",
        "ram_used_bytes": str(_ram_used_bytes()),
        "disk_read_bytes": str(max(0, dr1 - dr0)),
        "disk_write_bytes": str(max(0, dw1 - dw0)),
    }

    write_header = not csv_path.exists()
    with csv_path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=HW_FIELDS)
        if write_header:
            w.writeheader()
        w.writerow(row)

    # update state
    state[0], state[1], state[2], state[3] = idle1, total1, dr1, dw1


IPERF_FIELDS = ["snapshot_idx", "client", "event_time", "interval_start", "interval_end", "seconds", "bytes", "bits_per_second", "retransmits"]# Brief: Expected filename: <client>%<snapshot_idx>.<ext>
#  Example: cl0%3.json
def _parse_client_snapshot_from_name(p: Path) -> Tuple[Optional[int], str]:
    stem = p.stem  # cl0%3
    if "%" not in stem:
        return None, ""
    client, snap = stem.split("%", 1)
    try:
        return int(snap), client
    except Exception:
        return None, client


# Brief: iperf3 JSON usually has interval["sum"] for single-stream. 
#  If not present, fallback to streams[0]
def _safe_get_interval_sum(interval: Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(interval.get("sum"), dict):
        return interval["sum"]
    streams = interval.get("streams")
    if isinstance(streams, list) and streams and isinstance(streams[0], dict):
        # Each stream often has keys similar to sum; keep it best-effort.
        return streams[0]
    return {}

# Brief: Convert ALL *.json in `iperf_dir` into ONE CSV at `out_csv`
#  Adds columns: snapshot_idx, client (parsed from filename split by '%')
#  Writes one row per interval (e.g., 1s intervals if iperf ran with -i 1)
#  Returns stats dict: {"jsons": X, "rows": Y}

def snapshot_iperf_jsons_to_single_csv(
    iperf_dir: Path,
    out_csv: Path,
) -> Dict[str, int]:
    iperf_dir = Path(iperf_dir)
    out_csv = Path(out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    jsons = sorted(iperf_dir.glob("*.json"))
    total_rows = 0
    bsb_tz = timezone(timedelta(hours=-3))

    with out_csv.open("w", newline="", encoding="utf-8") as f_out:
        w = csv.DictWriter(f_out, fieldnames=IPERF_FIELDS)
        w.writeheader()

        for js in jsons:
            snap_idx, client = _parse_client_snapshot_from_name(js)
            snap_val = snap_idx if snap_idx is not None else ""

            try:
                raw = js.read_text(encoding="utf-8", errors="ignore").strip()
                if not raw:
                    continue
                data = json.loads(raw)
            except Exception:
                # Skip malformed JSON files
                continue

            start_ts = data.get("start", {}).get("timestamp", {}).get("timesecs", 0)

            intervals = data.get("intervals", [])
            if not isinstance(intervals, list) or not intervals:
                continue

            for interval in intervals:
                if not isinstance(interval, dict):
                    continue

                s = _safe_get_interval_sum(interval)
                if not isinstance(s, dict) or not s:
                    continue

                interval_start = float(s.get("start", 0))
                event_unix_time = start_ts + interval_start
                
                if start_ts > 0:
                    dt_obj = datetime.fromtimestamp(event_unix_time, tz=bsb_tz)
                    event_time_str = dt_obj.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] 
                else:
                    event_time_str = ""

                row = {
                    "snapshot_idx": str(snap_val),
                    "client": str(client),
                    "event_time": event_time_str,
                    "interval_start": str(s.get("start", "")),
                    "interval_end": str(s.get("end", "")),
                    "seconds": str(s.get("seconds", "")),
                    "bytes": str(s.get("bytes", "")),
                    "bits_per_second": str(s.get("bits_per_second", "")),
                    "retransmits": str(s.get("retransmits", "")),
                }
                w.writerow(row)
                total_rows += 1

    return {"jsons": len(jsons), "rows": total_rows}

PING_FIELDS = [
    "snapshot_idx",
    "client",
    "timestamp",
    "bytes",
    "target_ip",
    "icmp_seq",
    "ttl",
    "time_ms",
]

# Brief: Parses standard ping and ping -D (timestamped) output lines
# Example 1: 64 bytes from 192.168.0.1: icmp_seq=1 ttl=64 time=10.5 ms
# Example 2: [1708726543.123456] 64 bytes from 192.168.0.1: icmp_seq=2 ttl=64 time=11.2 ms
_PING_RE = re.compile(
    r"^(?:\[([\d\.]+)\]\s+)?(\d+)\s+bytes\s+from\s+([a-fA-F0-9\.:]+):\s+icmp_seq=(\d+)\s+ttl=(\d+)\s+time=([\d\.]+)\s*ms"
)

# Brief: Convert all ping output text files in `ping_dir` into ONE CSV at `out_csv`
#  Adds columns: snapshot_idx, client (parsed from filename split by '%')
#  If ran with ping -D, parses the UNIX timestamp
#  Returns stats dict: {"files": X, "rows": Y}
def snapshot_pings_to_single_csv(
    ping_dir: Path,
    out_csv: Path,
) -> Dict[str, int]:
    ping_dir = Path(ping_dir)
    out_csv = Path(out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    # Ping outputs are saved as .txt logs
    txt_files = sorted(ping_dir.glob("*.txt"))
    total_rows = 0

    with out_csv.open("w", newline="", encoding="utf-8") as f_out:
        w = csv.DictWriter(f_out, fieldnames=PING_FIELDS)
        w.writeheader()

        for txt in txt_files:
            snap_idx, client = _parse_client_snapshot_from_name(txt)
            snap_val = snap_idx if snap_idx is not None else ""
            
            # Fallback if filename is just "client.txt" without %
            if not client:
                client = txt.stem

            try:
                with txt.open("r", encoding="utf-8", errors="ignore") as f_in:
                    for line in f_in:
                        line = line.strip()
                        m = _PING_RE.match(line)
                        if m:
                            row = {
                                "snapshot_idx": str(snap_val),
                                "client": str(client),
                                "timestamp": m.group(1) if m.group(1) else "",
                                "bytes": m.group(2),
                                "target_ip": m.group(3),
                                "icmp_seq": m.group(4),
                                "ttl": m.group(5),
                                "time_ms": m.group(6),
                            }
                            w.writerow(row)
                            total_rows += 1
            except Exception:
                # Skip unreadable files
                continue

    return {"files": len(txt_files), "rows": total_rows}
