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
from onos_topologies.dash_topology.constants import DEBUG_CONFIG


if __name__ == "__main__":
    ROTATE_S = 120 # 2 minutes per snapshot
    DISPLAY_FILTER = None
    BPF_FILTER = ""
    #BPF_FILTER = "(tcp port 80 or tcp port 443 or icmp)"

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
    }
    (run_root / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    try:
        log.info("[RESET] utils.cleanup() (pre)")
        utils.cleanup() 

        topo = DashTopology(config=DEBUG_CONFIG, results_dir=run_root)
        topo.run(run_discovery=run_discovery)

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
            pcaps_dir = snap_dir / "tcpdump"
            ovs_dir.mkdir(parents=True, exist_ok=True)
            pcaps_dir.mkdir(parents=True, exist_ok=True)

            utils.append_event(run_root, f"SNAPSHOT_{snap_idx}_START {ts}")

            # Start tcpdump on each switch interface, writing straight into this snapshot/
            for pop, sw in topo.switches.items():
                swname = sw.getNodeName()
                capture_path = f"/results/dash/snapshots/snapshot_{snap_idx}/tcpdump"

                nodes = list(topo.hosts_by_pop.get(pop, []))

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

            # OVS snapshot for every switch (end of snapshot window)
            utils.snapshot_ovs_state(
                switch_names=[sw.getNodeName() for sw in topo.switches.values()],
                outdir=ovs_dir,
                of_version="OpenFlow13",
                parse_csv=True,
            )

            # Build ONE merged CSV for this snapshot
            packet_flow_csv = pcaps_dir / "packet_flow.csv"
            stats = utils.snapshot_pcaps_to_single_csv(
                tcpdump_dir=pcaps_dir,
                out_csv=packet_flow_csv,
                display_filter=DISPLAY_FILTER,
                delete_pcaps=True,  # set False if you want to keep pcaps for debugging
            )
            log.info(f"[PCAP->CSV] snapshot_{snap_idx}: pcaps={stats['pcaps']} rows={stats['rows']} -> {packet_flow_csv}")
            utils.append_event(run_root, f"SNAPSHOT_{snap_idx}_END {time.strftime('%Y%m%d-%H%M%S')}")
            snap_idx += 1

    except KeyboardInterrupt:
        log.info("[CONTINUOUS] Stop requested.")

    finally:
        utils.append_event(run_root, f"CONTINUOUS_STOP {int(time.time())}")

        final_stats = utils.merge_all_snapshot_csvs(
            run_root=Path(run_root),             
            out_csv_name="packet_flow_all.csv",
            delete_inputs=False,                  
        )

        log.info(
            f"[CSV-MERGE] files={final_stats['files']} rows={final_stats['rows']} -> "
            f"{Path(run_root) / 'packet_flow_all.csv'}"
        )

        try:
            utils.cleanup()
        except Exception:
            pass

    raise SystemExit(0)
