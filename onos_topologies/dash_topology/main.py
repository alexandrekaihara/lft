import sys
import time
import json
from pathlib import Path

# add project root to sys.path
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from onos_topologies.dash_topology.dash_topology import DashTopology
from onos_topologies.dash_topology import utils
from onos_topologies.dash_topology.constants import DEFAULT_CONFIG

if __name__ == "__main__":
    utils.cleanup()
    try:
        ans_custom = input("Do you want to configure the topology interactively (Hosts, QoS, etc.)? [y/N] ").strip().lower()        
        if ans_custom == 'y':
            # collect input and create a custom configuration dictionary
            final_config = utils.get_custom_config(DEFAULT_CONFIG)
        else:
            final_config = DEFAULT_CONFIG

        topology = DashTopology(config=final_config)
        
        # overwrite defaults if running interactively
        ans_discover = input("Do you want the controller to discover all hosts? [y/N] ").strip().lower()
        skip_discovery = True if ans_discover == 'n' else False

        ans_test = input("Run quick tests (ping/curl)? [y/N] ").strip().lower()
        run_tests = True if ans_test == 'y' else False
        
        ans_diagnostics = input("Run QoS diagnostics (tc qdisc + ping RTT)? [y/N] ").strip().lower()
        run_qos_diagnostics = True if ans_diagnostics == 'y' else False

        topology.run(
                    run_tests=run_tests, 
                    skip_discovery=skip_discovery, 
                    run_qos_diagnostics=run_qos_diagnostics
                    )
        
        ans_cont_dash = input("Run continuous DASH diagnostics every 10 minutes? [y/N] ").strip().lower()
        if ans_cont_dash == "y":
            interval_s = 600

            # host datadir (local folder next to main.py)
            datadir_root = Path(__file__).resolve().parent / "datadir"

            run_id = time.strftime("run_%Y-%m-%d_%H-%M-%S")
            run_root = datadir_root / run_id
            run_root.mkdir(parents=True, exist_ok=True)

            # saves run metadata
            meta = {
                "start_ts": int(time.time()),
                "config": final_config,
                "interval_s": interval_s,
                "n_clients": len(topology.clients),
            }
            (run_root / "meta.json").write_text(json.dumps(meta, indent=2))

            iter_idx = 0
            while True:
                iter_dir = run_root / f"iter_{iter_idx:04d}"
                # this already creates iter_dir/clients/ on the host automatically!
                topology.run_diagnostics_round(iter_dir=str(iter_dir), scheme="http")
                # topology.run_diagnostics_round(iter_dir=str(iter_dir), scheme="https")
                iter_idx += 1
                print(f"[DIAG] Sleeping {interval_s}s until next round...\n")
                time.sleep(interval_s) # sleeps for 10 min

    except KeyboardInterrupt:
        print("\n[INFO] Execution interrupted by user. Stopping.")
        utils.cleanup()
        sys.exit(0)
    except Exception as e:
        print(f"\n[FATAL ERROR] An unexpected error occurred: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        print("\n[INFO] Attempting to run cleanup before exiting...")
        utils.cleanup()
        sys.exit(1)
        
