import os, sys, time, json, subprocess, requests
from constants import CONFIG
from pathlib import Path
from threading import Thread
from werkzeug.serving import make_server

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from onos_topologies.dash_topology.dash_topology import DashTopology
from onos_topologies.dash_topology import utils

if __name__ == "__main__":
    """
        Step: Defining Experiment Constants
    """
    ROTATE_S = 60 # 1 minute per snapshot
    DEGRADED_ITERS = {2, 4}
    server_name = "ds0" # get the container name statically
    server_ip = "192.168.0.1"
    base_url_deployer = "http://127.0.0.1:5000/deploy"


    """
        Step: Input Handling
    """
    results_root = project_root / "results" / "iperf" # lft/results/iperf
    results_root.mkdir(parents=True, exist_ok=True)
    algorithm = ''
    while algorithm not in {'1', '2', '3'}:
        algorithm = (input(
            "Choose a number for the experiment: " \
            "\n[1] - cdn-qoe\n[2] - LLM\n[3] - Treshold\n"
            ).strip().lower())

    custom_name = (input(
        "Would you like to add a custom name to the results directory? [y/N]"
        ).strip().lower() == "y")

    if (custom_name):
        filename = input("Please type in the name of the file: ").strip().lower()
        run_root = results_root / f"{filename}"
    else:
        run_root = results_root / f"run_{time.strftime('%Y-%m-%d_%H-%M-%S')}"


    """
        Step: Create run directory and metadata json
    """
    run_root.mkdir(parents=True, exist_ok=True) # lft/results/iperf/run_...
    os.environ["LFT_RESULTS"] = str(run_root)

    snaps_root = run_root / "snapshots" # lft/results/iperf/run_.../snapshots
    snaps_root.mkdir(parents=True, exist_ok=True)

    meta = {
        "algorithm": algorithm,
        "start_ts": int(time.time()),
        "rotate_s": f"{ROTATE_S}s"
    }
    # Create metadata JSON inside run_root
    (run_root / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    try:
        utils.cleanup() # prune and kill containers

        """
            Step: Create and run the topology, alongside with the TCP iperf server and deployer
        """
        topo = DashTopology(config=CONFIG, results_dir=run_root, iperf=True, ospf=True)
        topo.run(run_discovery=True, disable_fwd=False)
        topo.servers[server_name].startServer(port=5201) # grabs the server obj and runs it

        print("\n[SETUP] Start the deployer in another terminal:")
        print("  cmd: docker run --rm -it --network host --name deployer deployer ")
        utils.sleep_countdown(t=30)


        """
            Step: hardcode link properties
        """
        # 'Clean' veth properties
        subprocess.run(f"sudo docker exec s0 tc qdisc del dev s0s2 root 2>/dev/null || true",shell=True)
        subprocess.run(f"sudo docker exec s2 tc qdisc del dev s2s0 root 2>/dev/null || true",shell=True)

        # Make RJ <-> ES the bottleneck, though it won't be degraded
        # Ideally, routing algos will choose MG <-> ES befogre degrading and RJ <-> ES after
        topo.switches["PoP-RJ"].setInterfaceProperties("s1s0", throughput="500mbit", delay="20ms", jitter="0ms")
        topo.switches["PoP-ES"].setInterfaceProperties("s0s1", throughput="500mbit", delay="20ms", jitter="0ms")

        # Prints the starting time of execution and saves the stdout string into events.log
        utils.append_event(run_root, f"CONTINUOUS_START {int(time.time())}")


        """
            Step: Snapshot Logic
        """
        snap_idx = 1
        # Each iteration corresponds to a snapshot
        while snap_idx <= 6:


            """
                Step: Degrade link (s0s1, s1s0)
            """
            # clear previous properties to allow reconfiguration
            subprocess.run(f"sudo docker exec s0 tc qdisc del dev s0s1 root 2>/dev/null || true",shell=True)
            subprocess.run(f"sudo docker exec s1 tc qdisc del dev s1s0 root 2>/dev/null || true",shell=True)

            # Link to be degraded: (if: s1s0, peer_if: s0s1)
            if (snap_idx in DEGRADED_ITERS):
                # Degrades link (throughput = 500 MBits)

                # Uses TC bidirectionally. Link = veth pair
                topo.switches["PoP-MG"].setInterfaceProperties("s1s0", throughput="100mbit", delay="100ms", jitter="0ms")
                topo.switches["PoP-ES"].setInterfaceProperties("s0s1", throughput="100mbit", delay="100ms", jitter="0ms")

            else:
                # Link goes back to normal (throughput = 1 GBit)
                topo.switches["PoP-MG"].setInterfaceProperties("s1s0", throughput="1000mbit", delay="10ms", jitter="0ms")
                topo.switches["PoP-ES"].setInterfaceProperties("s0s1", throughput="1000mbit", delay="10ms", jitter="0ms")


            """
                Step: Generate logs for Interface Properties
            """
            link_properties = subprocess.run(f"sudo tc qdisc show", shell=True, check=True, capture_output=True, text=True)
            utils.append_event(run_root, f"SNAPSHOT_{snap_idx}: {link_properties}")


            """ 
                Step: Active, for every client, a service by sending a request/intent to the deployer
            """
            if (algorithm == '1'): # cdn-qoe
                service = 'cdn-qoe'
            elif (algorithm == '2'): # LLM
                service = 'LLM'
            elif (algorithm == '3'): # Treshold
                service = 'Treshold'
            # For every client, request a service from the deployer by sending an intent
            for client_ip in topo.client_ip_range:
                # ex: "intent": "define intent q1: from endpoint('192.168.0.4') add service('cdn-qoe')"
                payload = {
                    "intent": f"define intent q1: from endpoint('{client_ip}') add service('{service}')"
                }
                response = requests.post(base_url_deployer, json=payload)

                if response.status_code == 200:
                    print(f"[OK] Service {service} for client {client_ip} was activated!")
                else:
                    print(f"Request failed with status code {response.status_code}")
                    print("Error message:", response.text)


            """
                Step: Results directory handling
            """
            ts = time.strftime("%Y%m%d-%H%M%S")
            snap_dir = snaps_root / f"snapshot_{snap_idx}"
            ovs_dir = snap_dir / "ovs"
            iperf_dir = snap_dir / "iperf"
            ovs_dir.mkdir(parents=True, exist_ok=True)
            iperf_dir.mkdir(parents=True, exist_ok=True)
            utils.append_event(run_root, f"SNAPSHOT_{snap_idx}_START {ts}")


            """
                Step: After intent activation and link degradation, run traffic using iperf
            """
            # Run iperf3 on every client and send JSON results to snapshot_X/iperf/<client>%<snapshot>.json
            iperf_jobs = []
            for client_name in topo.clients.keys():
                out_json = iperf_dir / f"{client_name}%{snap_idx}.json"

                cmd = [
                    "docker", "exec", client_name, "bash", "-lc",
                    f"iperf3 -c {server_ip} -p 5201 -t {ROTATE_S} -i 1 -J --get-server-output"
                ]

                f_out = open(out_json, "w", encoding="utf-8")
                # Runs iperf and stores proc to kill it later
                proc = subprocess.Popen(cmd, stdout=f_out, stderr=subprocess.STDOUT, text=True)
                iperf_jobs.append((proc, f_out, client_name))

            # wait iperf3 to finish and close JSON files
            for proc, f_out, _cname in iperf_jobs:
                try:
                    proc.wait(timeout=ROTATE_S + 15) # ROTATE_S=60 
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
                finally:
                    try:
                        f_out.close()
                    except Exception:
                        pass
            time.sleep(2)

            # OVS snapshot for every switch (end of snapshot window)
            utils.snapshot_ovs_state(
                switch_names=[sw.getNodeName() for sw in topo.switches.values()],
                outdir=ovs_dir,
                of_version="OpenFlow13",
                parse_csv=True,
                snapshot_idx=snap_idx,
            )

            # Build ONE merged CSV for this snapshot from the .json generated by iperf3
            iperf_csv = iperf_dir / "iperf_flow.csv"
            iperf_stats = utils.snapshot_iperf_jsons_to_single_csv(
                iperf_dir=iperf_dir,
                out_csv=iperf_csv,
            )

            utils.append_event(run_root, f"SNAPSHOT_{snap_idx}_END {time.strftime('%Y%m%d-%H%M%S')}")
            snap_idx += 1

    except KeyboardInterrupt:
        print("[CONTINUOUS] Stop requested.")

    finally:
        utils.append_event(run_root, f"CONTINUOUS_STOP {int(time.time())}")

        final_stats = utils.merge_all_snapshot_csvs(
            run_root=Path(run_root),             
            out_csv_name="packet_flow_all.csv",
            delete_inputs=False,                  
        )

        ovs_stats = utils.merge_all_snapshot_ovs_csvs(
            run_root=Path(run_root),
            delete_inputs=False,
        )

        iperf_final = utils.merge_all_snapshot_csvs(
            run_root=Path(run_root),
            out_csv_name="iperf_flow_all.csv",
            glob_pattern="snapshots/snapshot_*/iperf/iperf_flow.csv",
            delete_inputs=False,
        )

        try:
            utils.cleanup()
        except Exception:
            pass

    raise SystemExit(0)

