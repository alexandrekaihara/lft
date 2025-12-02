import os
import sys
import time
import json
import logging
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from onos_topologies.dash_topology.dash_topology import DashTopology
from onos_topologies.dash_topology import utils
from onos_topologies.dash_topology.constants import DEFAULT_CONFIG


if __name__ == "__main__":
    ROTATE_S = 600  # 10 minutes per snapshot
    DISPLAY_FILTER = None
    BPF_FILTER = "(tcp port 80 or tcp port 443 or icmp)"

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

        topo = DashTopology(config=DEFAULT_CONFIG, results_dir=run_root)
        topo.run(skip_discovery=skip_discovery)

        utils.append_event(run_root, f"CONTINUOUS_START {int(time.time())}")

        log.info(f"[CONTINUOUS] Snapshot every {ROTATE_S} minutes. Ctrl+C to stop.")
        snap_idx = 1

        # To run some tests
        client_names = sorted(topo.clients.keys()) # ["cl0","cl1","cl2",...]
        cl_idx = 0
        test_phase = 0 # 0=ICMP, 1=curl, 2=dash-client

        # Each execution corresponds to a snapshot
        while True:
            ts = time.strftime("%Y%m%d-%H%M%S")
            snap_dir = snaps_root / f"snapshot_{snap_idx}"
            ovs_dir = snap_dir / "ovs"
            pcaps_dir = snap_dir / "pcaps"
            ovs_dir.mkdir(parents=True, exist_ok=True)
            pcaps_dir.mkdir(parents=True, exist_ok=True)

            utils.append_event(run_root, f"SNAPSHOT_{snap_idx}_START {ts}")

            # Start tcpdump on each switch interface, writing straight into this snapshot/
            for pop, sw in topo.switches.items():
                swname = sw.getNodeName()
                capture_path = f"/results/dash/snapshots/snapshot_{snap_idx}/pcaps/{swname}"

                nodes = list(topo.clients_by_pop.get(pop, []))
                if pop == topo.server_pop_name and topo.server is not None:
                    nodes.append(topo.server)

                # Start a new tcpdump every snapshot (per interface). It auto-stops after ROTATE_S via the timeout flag, so it doesn't accumulate
                sw.collectFlowsTcpdump(
                    nodes=nodes,
                    path=capture_path,
                    rotateInterval=ROTATE_S,
                    sniffAll=False,
                    bpf_filter=BPF_FILTER,
                    snapshot_idx=snap_idx,
                )

            # Wait the capture window to finish
            time.sleep(ROTATE_S)
            time.sleep(2)

            # OVS snapshot for every switch
            utils.snapshot_ovs_state(
                switch_names=[sw.getNodeName() for sw in topo.switches.values()],
                outdir=ovs_dir,
                of_version="OpenFlow13",
                parse_csv=True,
            )

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

        # Delete all pcaps
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
