import os
import sys
import time
import json
import logging
import random
import subprocess
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from onos_topologies.dash_topology.dash_topology import DashTopology
from onos_topologies.dash_topology import utils
from onos_topologies.dash_topology.constants import DEFAULT_CONFIG


def run_dash_clients_batch(client_batch: list[str], server_ips: list[str], scheme: str = "http") -> None:
    procs: list[subprocess.Popen] = []

    for cname in client_batch:
        srv = random.choice(server_ips)
        cmd = (
            f"sudo docker exec {cname} bash -lc "
            f"\"/usr/local/bin/dash-client -y -hostname {srv} -scheme {scheme}\""
        )
        print(f"[DIAG] start {cname} -> server {srv}")
        procs.append(subprocess.Popen(cmd, shell=True))

    for p in procs:
        p.wait()


if __name__ == "__main__":
    ROTATE_S = 120  # 2 minutes per snapshot
    DISPLAY_FILTER = None
    BPF_FILTER = "(tcp port 80 or tcp port 443 or icmp)"

    # Cumulative load plan: 25, 50, 75, 100
    BATCH_SIZES = [25, 50, 75, 100]
    MAX_CLIENTS = 100  # Use exactly 100 clients as requested

    results_root = project_root / "results" / "dash"
    results_root.mkdir(parents=True, exist_ok=True)

    run_discovery = (input("Controller host discovery? [y/N] ").strip().lower() == "y")

    run_root = results_root / f"run_{time.strftime('%Y-%m-%d_%H-%M-%S')}"
    run_root.mkdir(parents=True, exist_ok=True)
    os.environ["LFT_RESULTS"] = str(run_root)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler(run_root / "run.log", encoding="utf-8"), logging.StreamHandler(sys.stdout)],
    )
    log = logging.getLogger("lft")

    snaps_root = run_root / "snapshots"
    snaps_root.mkdir(parents=True, exist_ok=True)

    meta = {
        "run_id": run_root.name,
        "start_ts": int(time.time()),
        "run_discovery": run_discovery,
        "run_root": str(run_root),
        "rotate_s": f"{ROTATE_S}s",
        "bpf_filter": BPF_FILTER,
        "experiment": "4 snapshots, cumulative clients 25/50/75/100, random server among ALL servers",
        "max_clients": MAX_CLIENTS,
    }
    (run_root / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    try:
        log.info("[RESET] utils.cleanup() (pre)")
        utils.cleanup()

        topo = DashTopology(config=DEFAULT_CONFIG, results_dir=run_root)
        topo.run(run_discovery=run_discovery)

        server_ips = list(topo.server_ip_range)
        if not server_ips:
            raise RuntimeError("No server IPs found in topo.server_ip_range")

        utils.append_event(run_root, f"EXPERIMENT_START {int(time.time())}")
        client_names = sorted(topo.clients.keys())

        client_pool = client_names[:MAX_CLIENTS]
        log.info(f"[EXPERIMENT] ROTATE_S={ROTATE_S}s, servers={server_ips}, total_clients_pool={len(client_pool)}")

        for snap_idx, k in enumerate(BATCH_SIZES, start=1):
            ts = time.strftime("%Y%m%d-%H%M%S")
            snap_dir = snaps_root / f"snapshot_{snap_idx}"
            ovs_dir = snap_dir / "ovs"
            pcaps_dir = snap_dir / "pcaps"
            ovs_dir.mkdir(parents=True, exist_ok=True)
            pcaps_dir.mkdir(parents=True, exist_ok=True)

            utils.append_event(run_root, f"SNAPSHOT_{snap_idx}_START {ts}")

            # Start tcpdump on each switch host-facing interface set.
            for pop, sw in topo.switches.items():
                swname = sw.getNodeName()
                capture_path = f"/results/dash/snapshots/snapshot_{snap_idx}/pcaps/{swname}"

                nodes = list(topo.hosts_by_pop.get(pop, []))
                if not nodes:
                    log.info(f"[tcpdump] skip {swname} (no host-facing nodes for pop={pop})")
                    continue

                sw.collectFlowsTcpdump(
                    nodes=nodes,
                    path=capture_path,
                    rotateInterval=ROTATE_S,
                    sniffAll=False,
                    bpf_filter=BPF_FILTER,
                    snapshot_idx=snap_idx,
                )

            # Cumulative batch: first k clients (includes previous ones).
            k_eff = min(k, len(client_pool))
            batch = client_pool[:k_eff]
            log.info(f"[EXPERIMENT] snapshot_{snap_idx}: running cumulative dash-client k={k_eff}")

            # Keep the snapshot window roughly equal to ROTATE_S.
            t0 = time.time()
            if batch:
                run_dash_clients_batch(batch, server_ips, scheme="http")
            elapsed = time.time() - t0
            remaining = max(0.0, ROTATE_S - elapsed)
            time.sleep(remaining)
            time.sleep(2)

            utils.snapshot_ovs_state(
                switch_names=[sw.getNodeName() for sw in topo.switches.values()],
                outdir=ovs_dir,
                of_version="OpenFlow13",
                parse_csv=True,
            )

            log.info(f"[OK] snapshot_{snap_idx} -> {snap_dir}")
            utils.append_event(run_root, f"SNAPSHOT_{snap_idx}_END {time.strftime('%Y%m%d-%H%M%S')}")

    except KeyboardInterrupt:
        log.info("[EXPERIMENT] Stop requested.")

    finally:
        utils.append_event(run_root, f"EXPERIMENT_STOP {int(time.time())}")

        log.info("[PARSE] Converting all snapshot PCAPs to CSV (in-place)...")
        parsed = 0
        pcaps = list(snaps_root.rglob("*.pcap"))

        for pcap in pcaps:
            out_csv = pcap.with_suffix(".csv")
            if out_csv.exists():
                continue
            try:
                utils.pcap_to_csv(pcap, out_csv, display_filter=DISPLAY_FILTER)
                parsed += 1
            except Exception as e:
                log.exception(f"[PARSE] Failed for {pcap}: {e}")
        log.info(f"[PARSE] Done. csv_created={parsed}")

        deleted = 0
        for pcap in pcaps:
            try:
                pcap.unlink(missing_ok=True)
                deleted += 1
            except Exception:
                log.exception(f"[CLEAN] Failed to delete {pcap}")

        log.info("[RESET] utils.cleanup() (post)")
        try:
            utils.cleanup()
        except Exception:
            pass

    raise SystemExit(0)
