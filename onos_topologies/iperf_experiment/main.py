import os, sys, time, json, subprocess, requests
from constants import CONFIG
from pathlib import Path
from threading import Thread
from werkzeug.serving import make_server

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from onos_topologies.dash_topology.dash_topology import DashTopology
from onos_topologies.dash_topology import utils

def get_network_summary(topo):
    lines = ["\n" + "="*60]
    lines.append(" [LINK INSPECTION] Current Ports Status (tc)")
    
    links_to_check = [
        ("MG (s1)", "s1s0"), ("ES (s0)", "s0s1"),
        ("RJ (s2)", "s2s0"), ("ES (s0)", "s0s2")
    ]
    
    for sw_name, interface in links_to_check:
        sw_id = sw_name.split('(')[1].replace(')', '')
        cmd = f"docker exec {sw_id} tc qdisc show dev {interface}"
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        clean_res = res.stdout.replace("qdisc netem 90d4: root refcnt 2 ", "").strip()
        lines.append(f" {sw_name} [{interface}]: {clean_res}")
        
    lines.append("="*60 + "\n")
    return "\n".join(lines)


if __name__ == "__main__":
    """
        Step: Defining Experiment Constants
    """
    ROTATE_S = 120 # 10 minutes per snapshot
    DEGRADED_ITERS = {2, 5}
    server_name = "ds0" # get the container name statically
    server_ip = "192.168.0.1"
    base_url_deployer = "http://127.0.0.1:5000/deploy"


    """
        Step: Input Handling
    """
    results_root = project_root / "results" / "iperf" # lft/results/iperf
    results_root.mkdir(parents=True, exist_ok=True)
    algorithm = ''
    while algorithm not in {'1', '2', '3', '4'}:
        algorithm = (input(
            "Choose a number for the experiment: " \
            "\n[1] - cdn-qoe\n[2] - LLM\n[3] - Treshold\n[4] - fwd\n[5] - ifwd\n"
            ).strip().lower())

    hindering = ''
    while hindering not in {'degrade', 'take down'}:
        hindering = (input("Choose what you want to do with the MG <-> ES link: " \
                               "\n[1] - Degrade (lower throughput and increase delay)" \
                               "\n[2] - Take Down (for fwd and ifwd to notice)\n"
            ).strip().lower())
        if hindering == '1': hindering = 'degrade'
        elif hindering == '2': hindering = 'take down'

    custom_name = (input(
        "Would you like to add a custom name to the results directory? [y/N]\n"
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
    ping_jobs = []

    # Create metadata JSON inside run_root
    (run_root / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    try:
        utils.cleanup() # prune and kill containers

        """
            Step: Create and run the topology, alongside with the TCP iperf server and deployer
        """
        #if (algorithm == '4'): # ospf is only availabe under v2.0 for ONOS
        #    topo = DashTopology(config=CONFIG, results_dir=run_root, iperf=True, onos_version="onosproject/onos:1.15.0")
        topo = DashTopology(config=CONFIG, results_dir=run_root, iperf=True) # onos v2.5
        
        if (algorithm in {'1', '2', '3'}):
            topo.run(run_discovery=True, disable_fwd=True)
            c1 = topo.controller
            c1.activateONOSApps(server_ip=topo.onos_ip,
                                command='app activate org.onosproject.proxyarp')
        elif (algorithm == '4'):
            topo.run(run_discovery=True, disable_fwd=False)
        elif (algorithm == '5'):
            topo.run(run_discovery=True, disable_fwd=True)
            print(" [SETUP] Mode: Intent-Based Forwarding (ifwd)")
            # Activates ifwd
            c1 = topo.controller
            c1.activateONOSApps(server_ip=topo.onos_ip, 
                                command='app activate org.onosproject.ifwd')
        
        print(" [SETUP] Telemetry -> Real-Time Mode")
        comp = "com.maojianwei.link.quality.measurement.impl.MaoLinkQualityManager"
        karaf = "/home/onos/apache-karaf-4.2.14/bin/client -u karaf -p karaf"
        cmd_str = f"cfg set {comp} latencyAverageSize 1; cfg set {comp} probeInterval 500; cfg set {comp} calculateInterval 500"
        subprocess.run(f"echo '{cmd_str}' | sudo docker exec -i c1 {karaf}", 
                       shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        topo.servers[server_name].startServer(port=5201) # grabs the server obj and runs it

        print("\n[SETUP] Start the deployer in another terminal:")
        print("  cmd: sudo docker run --rm -it --network host -v /var/run/docker.sock:/var/run/docker.sock --name deployer deployer")
        utils.sleep_countdown(t=60)


        """
            Step: hardcode link properties
        """
        print(" [SETUP] Configurando gargalo estático RJ <-> ES...")
        # Make RJ (s2) <-> ES (s0) the bottleneck, though it won't be degraded
        # Ideally, routing algos will choose MG <-> ES before degrading and RJ <-> ES after
        subprocess.run("docker exec s2 tc qdisc replace dev s2s0 root netem delay 20ms rate 500mbit", shell=True)
        subprocess.run("docker exec s0 tc qdisc replace dev s0s2 root netem delay 20ms rate 500mbit", shell=True)
        msg = get_network_summary(topo)
        print(msg)
        utils.append_event(run_root, msg)

        # Prints the starting time of execution and saves the stdout string into events.log
        utils.append_event(run_root, f"CONTINUOUS_START {int(time.time())}")


        """
            Step: RTT measuring
        """
        ping_dir = run_root / "ping_logs"
        ping_dir.mkdir(parents=True, exist_ok=True)

        print(" [SETUP] Pinging from cl to srv...")
        for client_name in topo.clients.keys():
            out_txt = ping_dir / f"{client_name}.txt"
            f_out = open(out_txt, "w", encoding="utf-8")
            cmd = ["docker", "exec", client_name, "ping", server_ip, "-i", "0.5", "-D", "-O"]
            proc = subprocess.Popen(cmd, stdout=f_out, stderr=subprocess.STDOUT, text=True)
            ping_jobs.append((proc, f_out))


        """
            Step: Snapshot Logic
        """
        snap_idx = 1
        # Each iteration corresponds to a snapshot
        while snap_idx <= 6:


            """
                Step: Degrade or take down link MG <-> ES link (s0s1, s1s0)
            """

            if (hindering == 'degrade'):
                # clear previous properties to allow reconfiguration
                subprocess.run(f"sudo docker exec s0 tc qdisc del dev s0s1 root 2>/dev/null || true",shell=True)
                subprocess.run(f"sudo docker exec s1 tc qdisc del dev s1s0 root 2>/dev/null || true",shell=True)
                try:
                    # Link to be degraded: MG (s1) <-> ES (s0)
                    if (snap_idx in DEGRADED_ITERS):
                        msg = f"\n [DEGRADE] Snapshot {snap_idx}: Aplicando degradação no link MG <-> ES"
                        cmd_mg = "docker exec s1 tc qdisc replace dev s1s0 root netem delay 100ms rate 100mbit"
                        cmd_es = "docker exec s0 tc qdisc replace dev s0s1 root netem delay 100ms rate 100mbit"
                    else:
                        msg = f"\n [NORMAL] Snapshot {snap_idx}: Link MG <-> ES operando normalmente"
                        cmd_mg = "docker exec s1 tc qdisc replace dev s1s0 root netem delay 10ms rate 1000mbit"
                        cmd_es = "docker exec s0 tc qdisc replace dev s0s1 root netem delay 10ms rate 1000mbit"
                        
                    print(msg)
                    utils.append_event(run_root, msg)

                    subprocess.run(cmd_mg, shell=True, check=True)
                    subprocess.run(cmd_es, shell=True, check=True)
                except Exception as e:
                    print(f" [WARNING] Failed do change link properties: {e}")
            elif (hindering == 'take down'): 
                try:  
                    if (snap_idx in DEGRADED_ITERS):
                        msg = f" [FAILURE] Snapshot {snap_idx}: Taking down link MG <-> ES (IP LINK DOWN)"
                        cmd1, cmd2 = "sudo docker exec s1 ip link set s1s0 down", "sudo docker exec s0 ip link set s0s1 down"
                    else:
                        msg = f" [RECOVERY] Snapshot {snap_idx}: Restoring link MG <-> ES (IP LINK UP)"
                        cmd1, cmd2 = "sudo docker exec s1 ip link set s1s0 up", "sudo docker exec s0 ip link set s0s1 up"
                    
                    print(msg)
                    utils.append_event(run_root, msg)
                    subprocess.run(cmd1, shell=True, check=True)
                    subprocess.run(cmd2, shell=True, check=True)

                except Exception as e: 
                    print(f" [WARNING] Falha ao alterar as propriedades do link: {e}")


            """
                Step: Generate logs for Interface Properties
            """
            link_properties = subprocess.run(f"sudo tc qdisc show", shell=True, check=True, capture_output=True, text=True)
            utils.append_event(run_root, f"SNAPSHOT_{snap_idx}: {link_properties}")


            """ 
                Step: Active, for every client, a service by sending a request/intent to the deployer
            """
            if algorithm == '1':
                service = 'cdn-qoe'
            elif algorithm == '2':
                service = 'llm'
            elif algorithm == '3':
                service = 'treshold'
            elif algorithm == '4':
                service = 'fwd'
            elif algorithm == '5':
                service = 'ifwd'

            msg = " [WAIT] Waiting for ONOS telemetry (5s)..."
            print(msg)
            utils.append_event(run_root, msg)
            time.sleep(5)

            if algorithm in {'1', '2', '3'}: # fwd and ifwd don't need to send intents to the deployer
                # For every client, request a service from the deployer by sending an intent
                for raw_ip in topo.client_ip_range:
                    clean_ip = raw_ip.split('/')[0].strip()
                    payload = {"intent": f"define intent q1: from endpoint('{clean_ip}') add service('{service}')"}
                    
                    print(f"\n [SNAPSHOT {snap_idx}] Requesting {service} for {clean_ip}...")
                    try:
                        response = requests.post(base_url_deployer, json=payload, timeout=15)
                        if response.status_code in [200, 201]:
                            data = response.json()
                            # Gets frules installed to show on the terminal
                            ctrl_resps = data.get('controller_responses', {})
                            for ip, info in ctrl_resps.items():
                                flows = info.get('output', {}).get('responses', [])
                                print(f" [DEPLOYER] {len(flows)} flows installed by ONOS ({ip})")
                                for f in flows:
                                    f_id = f['location'].split('/')[-1]
                                    dpid = f['location'].split('/')[-2]
                                    print(f"    -> Flux {f_id} on Switch {dpid}")
                        else:
                            print(f" [ERRO] Deployer returned {response.status_code}")
                    except Exception as e:
                        print(f" [FALHA] Request error: {e}")

            msg = get_network_summary(topo)
            print(msg)
            utils.append_event(run_root, msg)

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

        for proc, f_out in ping_jobs:
            proc.kill()
            try:
                f_out.close()
            except Exception:
                pass

        ping_csv_out = run_root / "ping_flow_all.csv"
        ping_stats = utils.snapshot_pings_to_single_csv(
            ping_dir=run_root / "ping_logs",
            out_csv=ping_csv_out
        )
        print(f" [RESULTADOS] CSV de Ping gerado com {ping_stats['rows']} linhas.")

        try:
            utils.cleanup()
        except Exception:
            pass

    raise SystemExit(0)

