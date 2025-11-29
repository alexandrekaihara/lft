import os
import sys
import time
import uuid
import logging
import traceback
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from onos_topologies.dash_topology.dash_topology import DashTopology
from onos_topologies.dash_topology import utils
from onos_topologies.dash_topology.constants import DEFAULT_CONFIG


if __name__ == "__main__":
    # Results root config + LFT_DATADIR (host-side)
    results_root = project_root / "results" / "dash"
    os.environ.setdefault("LFT_DATADIR", str(results_root))

    # All runs will be @ $LFT_DATADIR/datadir/<run_id>/
    datadir_root = Path(os.environ["LFT_DATADIR"]) / "datadir"
    datadir_root.mkdir(parents=True, exist_ok=True)

    # Params
    N = int(input("How many repetitions (N)? [e.g., 10] ").strip() or "10")
    pause = input("Pause before traffic each rep (apply intent then ENTER)? [y/N] ").strip().lower() == "y"

    ans_custom = input("Do you want to configure the topology interactively (Hosts, QoS, etc.)? [y/N] ").strip().lower()
    final_config = utils.get_custom_config(DEFAULT_CONFIG) if ans_custom == "y" else DEFAULT_CONFIG

    ans_discover = input("Do you want the controller to discover all hosts? [y/N] ").strip().lower()
    skip_discovery = True if ans_discover == "n" else False

    run_id = f"run_{time.strftime('%Y-%m-%d_%H-%M-%S')}_{uuid.uuid4().hex[:8]}"
    run_root = datadir_root / run_id
    run_root.mkdir(parents=True, exist_ok=True)

    # Simple logger (console + file)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(run_root / "run.log", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    log = logging.getLogger("lft")

    # Metadata 
    utils.write_json(
        run_root / "meta.json",
        {
            "run_id": run_id,
            "start_ts": int(time.time()),
            "N": N,
            "config": final_config,
            "skip_discovery": skip_discovery,
            "lft_datadir": os.environ["LFT_DATADIR"],
            "capture": {
                "mode": "Switch.collectFlows (tshark inside each OVS switch container)",
                "container_path": "/results/dash/pcaps/<switch>/dump.pcap (rotating)",
                "host_path": str(run_root / "rep_xxxx" / "switch" / "pcaps"),
                "rotation": {"by": "duration", "seconds": 60},
                "scope": "Host-facing ports (nodes list per PoP); server included on server PoP",
            },
            "notes": [
                "No more before/after snapshots from a sidecar ring buffer.",
                "Capture is continuous during each repetition; use events.log timestamps to slice windows.",
            ],
        },
    )

    log.info(f"[RUN] {run_id} -> {run_root}")

    for rep in range(N):
        rep_id = f"rep_{rep:04d}"
        rep_dir = run_root / rep_id
        rep_dir.mkdir(parents=True, exist_ok=True)

        rep_manifest = {
            "run_id": run_id,
            "rep_id": rep_id,
            "start_ts": int(time.time()),
            "valid": True,
            "invalid_reason": None,
            "notes": [],
        }

        topo = None

        try:
            log.info(f"\n[REP] ===== START {rep_id} =====")
            log.info("[RESET] utils.cleanup() (pre)")
            utils.cleanup()

            # Bind mount root for switches (host path)
            switch_mount = rep_dir / "switch"
            switch_mount.mkdir(parents=True, exist_ok=True)

            # Create + run topology (this starts collectFlows internally)
            topo = DashTopology(config=final_config, results_dir=switch_mount)
            topo.run(skip_discovery=skip_discovery)

            if pause:
                log.info("[PAUSE] Apply intent/deployer now, then press ENTER to start traffic...")
                input()
                (rep_dir / "events.log").write_text(
                    f"PAUSE_RELEASED {int(time.time())}\n",
                    encoding="utf-8",
                )

            with (rep_dir / "events.log").open("a", encoding="utf-8") as f:
                f.write(f"TRAFFIC_START {int(time.time())}\n")

            iter_dir = rep_dir / "iter_0000"
            topo.run_diagnostics_round(iter_dir=str(iter_dir), scheme="http")

            # Switch stats snapshot @ the end of the experiment
            snapshot_dir = rep_dir / "switch_stats" / "end"
            snapshot_dir.mkdir(parents=True, exist_ok=True)

            switch_names = [sw.getNodeName() for sw in topo.switches.values()]
            utils.snapshot_ovs_state(
                switch_names=switch_names,
                outdir=snapshot_dir,
                of_version="OpenFlow13",
                parse_csv=True,
            )

            with (rep_dir / "events.log").open("a", encoding="utf-8") as f:
                f.write(f"SWITCH_STATS_SNAPSHOT_END {int(time.time())}\n")

            missing = utils.validate_rep_outputs(rep_dir, topo)
            if missing:
                rep_manifest["valid"] = False
                rep_manifest["invalid_reason"] = f"Missing dash output for clients: {missing}"
                (rep_dir / "INVALID").write_text(rep_manifest["invalid_reason"], encoding="utf-8")
                log.error(f"[INVALID] {rep_id}: {rep_manifest['invalid_reason']}")

        except Exception as e:
            rep_manifest["valid"] = False
            rep_manifest["invalid_reason"] = f"Exception: {e}"
            (rep_dir / "INVALID").write_text(rep_manifest["invalid_reason"], encoding="utf-8")
            log.error(traceback.format_exc())

        finally:
            rep_manifest["end_ts"] = int(time.time())
            utils.write_json(rep_dir / "manifest.json", rep_manifest)

            log.info("[RESET] utils.cleanup() (post)")
            try:
                utils.cleanup()
            except Exception:
                pass

            log.info(f"[REP] ===== END {rep_id} valid={rep_manifest['valid']} =====")

    log.info("[RUN] Finished.")
