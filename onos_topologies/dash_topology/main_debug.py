import os
import sys
import time
import json
import logging
import subprocess
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from onos_topologies.dash_topology.dash_topology import DashTopology
from onos_topologies.dash_topology import utils
from onos_topologies.dash_topology.constants import DEFAULT_CONFIG, DEBUG_ADJACENCY_MATRIX, DEBUG_POPS


def _run_and_wait(node, cmd: str, timeout_s: int, log, tag: str) -> None:
    res = node.run(cmd)

    # DashTopology Node.run is returning Popen
    if isinstance(res, subprocess.Popen):
        try:
            res.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            log.warning(f"[{tag}] timeout after {timeout_s}s, terminating...")
            try:
                res.terminate()
                res.wait(timeout=5)
            except Exception:
                try:
                    res.kill()
                except Exception:
                    pass
        return

    # If someday node.run starts returning text, still safe
    if isinstance(res, str) and res.strip():
        log.info(f"[{tag}] OUT: {res.strip()}")


# Brief: Sends 10 ICMP packets from a given client to the DASH server
# Expected result: in the PCAP you should see exactly 10 ICMP Echo Requests and 10 Echo Replies
def _test_icmp(client, server_ip: str, snap_idx: int, log) -> None:
    client_name = client.getNodeName()
    log.info(f"[TRAFFIC] ICMP snap={snap_idx} {client_name} -> {server_ip}")

    cmd = f'bash -lc "ping -c 10 -i 0.2 -W 1 {server_ip} -q"'
    _run_and_wait(client, cmd, timeout_s=15, log=log, tag=f"ICMP {client_name} snap={snap_idx}")


# Brief: Runs dash-client from a given client toward the DASH server
# Expected result: dash-client should generate HTTP traffic to the server
def _test_dash_client(client, server_ip: str, snap_idx: int, log) -> None:
    client_name = client.getNodeName()
    log.info(f"[TRAFFIC] DASH-CLIENT snap={snap_idx} {client_name} -> {server_ip}")

    cmd = f'bash -lc "timeout -s INT 25 /usr/local/bin/dash-client -y -hostname {server_ip} -scheme http"'
    _run_and_wait(client, cmd, timeout_s=30, log=log, tag=f"DASH-CLIENT {client_name} snap={snap_idx}")


if __name__ == "__main__":
    ROTATE_S = 60  # 10 minutes per snapshot (seconds)
    DISPLAY_FILTER = None
    BPF_FILTER = "(tcp port 80 or tcp port 443 or icmp)"

    config = DEFAULT_CONFIG
    config["adjacency_matrix"] = DEBUG_ADJACENCY_MATRIX
    config["pops"] = DEBUG_POPS

    results_root = project_root / "results" / "dash"
    results_root.mkdir(parents=True, exist_ok=True)

    skip_discovery = (input("Controller host discovery? [y/N] ").strip().lower() != "y")

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
        "skip_discovery": skip_discovery,
        "run_root": str(run_root),
        "rotate_s": f"{ROTATE_S}s",
        "bpf_filter": BPF_FILTER,
    }
    (run_root / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    try:
        log.info("[RESET] utils.cleanup() (pre)")
        utils.cleanup()

        topo = DashTopology(config=config, results_dir=run_root)
        topo.run(skip_discovery=skip_discovery)

        utils.append_event(run_root, f"CONTINUOUS_START {int(time.time())}")

        log.info(f"[CONTINUOUS] Snapshot every {ROTATE_S}s. Ctrl+C to stop.")
        snap_idx = 1

        client_names = sorted(topo.clients.keys())  # ["cl0","cl1","cl2",...]

        while True:
            t0 = time.monotonic()

            ts = time.strftime("%Y%m%d-%H%M%S")
            snap_dir = snaps_root / f"snapshot_{snap_idx}"
            ovs_dir = snap_dir / "ovs"
            pcaps_dir = snap_dir / "pcaps"
            ovs_dir.mkdir(parents=True, exist_ok=True)
            pcaps_dir.mkdir(parents=True, exist_ok=True)

            utils.append_event(run_root, f"SNAPSHOT_{snap_idx}_START {ts}")

            # Start tcpdump on each switch interface, writing straight into this snapshot
            for pop, sw in topo.switches.items():
                swname = sw.getNodeName()
                capture_path = f"/results/dash/snapshots/snapshot_{snap_idx}/pcaps/{swname}"

                nodes = list(topo.clients_by_pop.get(pop, []))
                if pop == topo.server_pop_name and topo.server is not None:
                    nodes.append(topo.server)

                # Start a new tcpdump per snapshot (per iface); it auto-stops after ROTATE_S via `timeout`
                sw.collectFlowsTcpdump(
                    nodes=nodes,
                    path=capture_path,
                    rotateInterval=ROTATE_S,
                    sniffAll=False,
                    bpf_filter=BPF_FILTER,
                    snapshot_idx=snap_idx,
                )

            # Traffic: run tests for all clients inside the snapshot window
            if not client_names:
                log.warning("[TRAFFIC] No clients found.")
            else:
                log.info(f"[TRAFFIC] Running tests for all clients: n={len(client_names)}")
                for cname in client_names:
                    cl = topo.clients[cname]
                    #_test_icmp(cl, topo.server_ip, snap_idx, log)
                    #_test_dash_client(cl, topo.server_ip, snap_idx, log)

            # OVS snapshot for every switch (keep it close to the traffic moment)
            utils.snapshot_ovs_state(
                switch_names=[sw.getNodeName() for sw in topo.switches.values()],
                outdir=ovs_dir,
                of_version="OpenFlow13",
                parse_csv=True,
            )

            # Wait only the remaining time of the capture window (prevents "cumulative" behavior)
            elapsed = time.monotonic() - t0
            if elapsed < ROTATE_S:
                time.sleep(ROTATE_S - elapsed)
            else:
                log.warning(f"[TIMING] snapshot_{snap_idx} overran window: elapsed={elapsed:.2f}s > ROTATE_S={ROTATE_S}s")

            time.sleep(2)  # small flush margin

            log.info(f"[OK] snapshot_{snap_idx} -> {snap_dir}")
            utils.append_event(run_root, f"SNAPSHOT_{snap_idx}_END {time.strftime('%Y%m%d-%H%M%S')}")
            snap_idx += 1

    except KeyboardInterrupt:
        log.info("[CONTINUOUS] Stop requested.")
    finally:
        utils.append_event(run_root, f"CONTINUOUS_STOP {int(time.time())}")

        # Parse EVERYTHING at the end, saving CSV next to each PCAP
        log.info("[PARSE] Converting all snapshot PCAPs to CSV (in-place)...")
        parsed = 0
        pcaps = list(snaps_root.rglob("*.pcap*"))

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

        # Delete all pcaps
        deleted = 0
        for pcap in pcaps:
            try:
                pcap.unlink(missing_ok=True)
                deleted += 1
            except Exception:
                log.exception(f"[CLEAN] Failed to delete {pcap}")
        log.info(f"[CLEAN] pcaps_deleted={deleted}")

        log.info("[RESET] utils.cleanup() (post)")
        try:
            utils.cleanup()
        except Exception:
            pass

    raise SystemExit(0)
