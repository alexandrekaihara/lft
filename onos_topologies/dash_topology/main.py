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


def append_event(rep_dir: Path, line: str) -> None:
    # Append one event line to events.log.
    rep_dir.mkdir(parents=True, exist_ok=True)
    with (rep_dir / "events.log").open("a", encoding="utf-8") as f:
        f.write(line.rstrip() + "\n")


if __name__ == "__main__":
    # Host-side results root + env var
    results_root = project_root / "results" / "dash"
    os.environ.setdefault("LFT_DATADIR", str(results_root))

    datadir_root = Path(os.environ["LFT_DATADIR"]) / "datadir"
    datadir_root.mkdir(parents=True, exist_ok=True)

    mode = (input("Execution mode [controlled/continuous]? [controlled] ").strip().lower() or "controlled")
    if mode not in ("controlled", "continuous"):
        mode = "controlled"

    ans_custom = input("Do you want to configure the topology interactively (Hosts, QoS, etc.)? [y/N] ").strip().lower()
    final_config = utils.get_custom_config(DEFAULT_CONFIG) if ans_custom == "y" else DEFAULT_CONFIG

    ans_discover = input("Do you want the controller to discover all hosts? [y/N] ").strip().lower()
    skip_discovery = True if ans_discover == "n" else False

    run_id = f"run_{time.strftime('%Y-%m-%d_%H-%M-%S')}_{uuid.uuid4().hex[:8]}"
    run_root = datadir_root / run_id
    run_root.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(run_root / "run.log", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    log = logging.getLogger("lft")

    # Minimal meta for traceability
    utils.write_json(
        run_root / "meta.json",
        {
            "run_id": run_id,
            "start_ts": int(time.time()),
            "mode": mode,
            "config": final_config,
            "skip_discovery": skip_discovery,
            "lft_datadir": os.environ["LFT_DATADIR"],
        },
    )

    log.info(f"[RUN] {run_id} -> {run_root}")

    if mode == "continuous":
        try:
            log.info("[RESET] utils.cleanup() (pre)")
            utils.cleanup()

            out_root = run_root / "continuous"
            out_root.mkdir(parents=True, exist_ok=True)

            topo = DashTopology(config=final_config, results_dir=out_root)
            topo.run(skip_discovery=skip_discovery)

            switch_names = [sw.getNodeName() for sw in topo.switches.values()]
            append_event(out_root, f"CONTINUOUS_START {int(time.time())}")

            rotate_s = 600 
            log.info(f"[CONTINUOUS] Snapshot period = {rotate_s}s. Press Ctrl+C to stop.")

            while True:
                ts = time.strftime("%Y%m%d-%H%M%S")
                snap_dir = out_root / "snapshots" / ts
                utils.snapshot_ovs_state(
                    switch_names=switch_names,
                    outdir=snap_dir,
                    of_version="OpenFlow13",
                    parse_csv=True,
                )
                append_event(out_root, f"SNAPSHOT {ts}")
                time.sleep(rotate_s)
        except KeyboardInterrupt:
            log.info("[CONTINUOUS] Stop requested.")
        finally:
            append_event(run_root / "continuous", f"CONTINUOUS_STOP {int(time.time())}")
            log.info("[RESET] utils.cleanup() (post)")
            try:
                utils.cleanup()
            except Exception:
                pass

        log.info("[RUN] Finished.")
        raise SystemExit(0)


    # Controlled mode
    N = int(input("How many repetitions (N)? [e.g., 10] ").strip() or "10")
    pause = input("Pause to apply intent between snapshots? [y/N] ").strip().lower() == "y"

    controlled_root = run_root / "controlled"
    controlled_root.mkdir(parents=True, exist_ok=True)

    for rep in range(N):
        rep_id = f"rep_{rep:04d}"
        rep_dir = controlled_root / rep_id
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

            topo = DashTopology(config=final_config, results_dir=rep_dir)
            topo.run(skip_discovery=skip_discovery)

            switch_names = [sw.getNodeName() for sw in topo.switches.values()]

            # Snapshot BEFORE (baseline)
            before_dir = rep_dir / "switch_stats" / "before"
            utils.snapshot_ovs_state(switch_names=switch_names, outdir=before_dir, of_version="OpenFlow13", parse_csv=True)
            append_event(rep_dir, f"SWITCH_SNAPSHOT_BEFORE {int(time.time())}")

            if pause:
                log.info("[PAUSE] Apply intent now, then press ENTER...")
                input()
                append_event(rep_dir, f"PAUSE_RELEASED {int(time.time())}")

            # Snapshot AFTER (closest possible to intent-applied state)
            after_dir = rep_dir / "switch_stats" / "after"
            utils.snapshot_ovs_state(switch_names=switch_names, outdir=after_dir, of_version="OpenFlow13", parse_csv=True)
            append_event(rep_dir, f"SWITCH_SNAPSHOT_AFTER {int(time.time())}")

            # Run DASH once (V0: one iteration per rep)
            append_event(rep_dir, f"TRAFFIC_START {int(time.time())}")
            iter_dir = rep_dir / "iter_0000"
            topo.run_diagnostics_round(iter_dir=str(iter_dir), scheme="http")
            append_event(rep_dir, f"TRAFFIC_END {int(time.time())}")

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
