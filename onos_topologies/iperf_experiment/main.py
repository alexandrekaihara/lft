import os, sys, time, json, subprocess, requests
from constants import CONFIG
from pathlib import Path

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


def start_ollama():
    print(" [MOTOR] Running Ollama...")
    subprocess.run("systemctl start ollama", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    print(" [MOTOR] Pre-loading Llama 3.1 in the memory...")
    try:
        requests.post("http://localhost:11434/api/generate", json={"model": "llama3.1", "keep_alive": "30m"}, timeout=5)
    except requests.exceptions.ReadTimeout:
        pass
    except Exception as e:
        print(f" [AVISO] Failed to pre-load LLM: {e}")


def restart_iperf_server(server_obj, server_name: str, port: int = 5201):
    print(f" [IPERF] Restarting iperf3 server on {server_name}:{port}...")
    subprocess.run(
        f"docker exec {server_name} pkill -f 'iperf3 -s' || true",
        shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    time.sleep(1)
    server_obj.startServer(port=port)
    time.sleep(2)
    # Confirm server is up
    check = subprocess.run(
        f"docker exec {server_name} ss -tlnp",
        shell=True, capture_output=True, text=True
    )
    if f":{port}" in check.stdout:
        print(f" [IPERF] Server confirmed listening on :{port}")
    else:
        print(f" [WARNING] Server may not be listening on :{port} — check manually!")


def debug_iperf_connectivity(client_name: str, server_ip: str, port: int = 5201):
    print(f" [DEBUG] Testing {client_name} -> {server_ip}:{port} (3s probe)...")
    result = subprocess.run(
        f"docker exec {client_name} iperf3 -c {server_ip} -p {port} -t 3 --connect-timeout 5000",
        shell=True, capture_output=True, text=True
    )
    if result.returncode == 0:
        print(f" [DEBUG] ✓ {client_name} reached {server_ip}")
        return True
    else:
        err = (result.stderr or result.stdout or "").strip()
        print(f" [DEBUG] ✗ {client_name} FAILED to reach {server_ip}: {err}")
        return False


MODES = {
    '1': {"name": "cdn-qoe",  "onos": "2.5.0", "disable_fwd": True,  "apps": "proxyarp", "use_deployer": True},
    '2': {"name": "llm",      "onos": "2.5.0", "disable_fwd": True,  "apps": "proxyarp", "use_deployer": True, "pre_run": "ollama"},
    '3': {"name": "treshold", "onos": "2.5.0", "disable_fwd": True,  "apps": "proxyarp", "use_deployer": True},
    '4': {"name": "fwd",      "onos": "2.5.0", "disable_fwd": False, "apps": "",         "use_deployer": False},
    '5': {"name": "ospf",     "onos": "1.6",   "disable_fwd": True,  "apps": "proxyarp", "use_deployer": False}
}


if __name__ == "__main__":
    """
        Step: Defining Experiment Constants
    """
    ROTATE_S = 600  # 10 minutes per snapshot
    DEGRADED_ITERS = {2, 5}
    server_name = "ds0"
    base_url_deployer = "http://127.0.0.1:5000/deploy"

    """
        Step: Input Handling
    """
    results_root = project_root / "results" / "iperf"
    results_root.mkdir(parents=True, exist_ok=True)
    algorithm = ''
    while algorithm not in {'1', '2', '3', '4', '5'}:
        algorithm = (input(
            "Choose a number for the experiment: "
            "\n[1] - cdn-qoe\n[2] - LLM\n[3] - Treshold\n[4] - fwd\n[5] - ospf\n"
            ).strip().lower())

    hindering = ''
    while hindering not in {'degrade', 'take down'}:
        hindering = (input(
            "Choose what you want to do with the MG <-> ES link: "
            "\n[1] - Degrade (lower throughput and increase delay)"
            "\n[2] - Take Down (for fwd and ifwd to notice)\n"
            ).strip().lower())
        if hindering == '1': hindering = 'degrade'
        elif hindering == '2': hindering = 'take down'

    custom_name = (input(
        "Would you like to add a custom name to the results directory? [y/N]\n"
        ).strip().lower() == "y")

    if custom_name:
        filename = input("Please type in the name of the file: ").strip().lower()
        run_root = results_root / f"{filename}"
    else:
        run_root = results_root / f"run_{time.strftime('%Y-%m-%d_%H-%M-%S')}"

    server_ip = "192.168.0.1" if algorithm != '5' else "192.168.10.10"

    """
        Step: Create run directory and metadata json
    """
    run_root.mkdir(parents=True, exist_ok=True)
    os.environ["LFT_RESULTS"] = str(run_root)

    snaps_root = run_root / "snapshots"
    snaps_root.mkdir(parents=True, exist_ok=True)

    meta = {
        "algorithm": algorithm,
        "start_ts": int(time.time()),
        "rotate_s": f"{ROTATE_S}s"
    }
    ping_jobs = []

    (run_root / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    mode_cfg = MODES.get(algorithm)
    service = mode_cfg["name"]

    if mode_cfg.get("pre_run") == "ollama":
        start_ollama()

    try:
        utils.cleanup()

        """
            Step: Create and run the topology
        """
        onos_tag = f"onosproject/onos:{mode_cfg['onos']}"
        topo = DashTopology(config=CONFIG, results_dir=run_root, iperf=True, onos_version=onos_tag)

        topo.run(run_discovery=True, disable_fwd=mode_cfg["disable_fwd"])
        c1 = topo.controller

        if mode_cfg["apps"]:
            print(f" [SETUP] Activating extra apps: {mode_cfg['apps']}")
            c1.activateONOSApps(server_ip=topo.onos_ip,
                                command=f"app activate org.onosproject.{mode_cfg['apps']}")

        print(" [SETUP] Telemetry -> Real-Time Mode")
        comp = "com.maojianwei.link.quality.measurement.impl.MaoLinkQualityManager"
        karaf = "/home/onos/apache-karaf-4.2.14/bin/client -u karaf -p karaf"
        cmd_str = f"cfg set {comp} latencyAverageSize 1; cfg set {comp} probeInterval 500; cfg set {comp} calculateInterval 500"
        subprocess.run(f"echo '{cmd_str}' | sudo docker exec -i c1 {karaf}",
                       shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Start iperf server for the first time
        topo.servers[server_name].startServer(port=5201)
        time.sleep(2)

        if mode_cfg.get("use_deployer", False):
            print("\n[SETUP] Start the deployer in another terminal:")
            print("  cmd: sudo docker run --rm -it --network host -v /var/run/docker.sock:/var/run/docker.sock --name deployer deployer")
            utils.sleep_countdown(t=60)
        else:
            print(f"\n [SETUP] Skipping Deployer (Mode {service} does not send intents to the deployer).")
            time.sleep(2)

        """
            Step: Hardcode link properties
        """
        print(" [SETUP] Configurando gargalo estático RJ <-> ES...")
        subprocess.run("docker exec s2 tc qdisc replace dev s2s0 root netem delay 20ms rate 500mbit", shell=True)
        subprocess.run("docker exec s0 tc qdisc replace dev s0s2 root netem delay 20ms rate 500mbit", shell=True)
        msg = get_network_summary(topo)
        print(msg)
        utils.append_event(run_root, msg)
        utils.append_event(run_root, f"CONTINUOUS_START {int(time.time())}")

        """
            Step: OSPF convergence wait
        """
        if algorithm == '5':
            print(" [WAIT] Waiting 40s for OSPF convergence...")
            time.sleep(40)

            # Confirm routing is ready before starting snapshots
            print(" [DEBUG] Post-convergence connectivity check...")
            reachable = debug_iperf_connectivity(
                client_name=list(topo.clients.keys())[0],
                server_ip=server_ip,
                port=5201
            )
            if not reachable:
                print(" [WARNING] Client cannot reach server after OSPF convergence!")
                print(f"  → Expected route: cl0 -> s3 -> (OSPF) -> s0 -> ds0 ({server_ip})")
                print(f"  → Check: docker exec cl0 ip route")
                print(f"  → Check: docker exec s0 ip route")
                utils.append_event(run_root, " [WARNING] Pre-snapshot connectivity check FAILED")
            else:
                utils.append_event(run_root, " [OK] Pre-snapshot connectivity check passed")

        """
            Step: Start ping monitoring
        """
        ping_dir = run_root / "ping_logs"
        ping_dir.mkdir(parents=True, exist_ok=True)

        print(" [SETUP] Pinging from cl to srv...")
        for client_name in topo.clients.keys():
            out_txt = ping_dir / f"{client_name}.txt"
            f_out = open(out_txt, "w", encoding="utf-8")
            cmd = ["sudo", "docker", "exec", client_name, "ping", server_ip, "-i", "0.5", "-D", "-O"]
            proc = subprocess.Popen(cmd, stdout=f_out, stderr=subprocess.STDOUT, text=True)
            ping_jobs.append((proc, f_out))

        """
            Step: Snapshot Loop
        """
        snap_idx = 1
        while snap_idx <= 6:
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
                Step: FIX — Restart iperf3 server before each snapshot
                Prevents "server busy" errors that produce empty JSON files.
            """
            restart_iperf_server(topo.servers[server_name], server_name, port=5201)

            """
                Step: Degrade or take down link MG <-> ES
            """
            if hindering == 'degrade':
                subprocess.run("sudo docker exec s0 tc qdisc del dev s0s1 root 2>/dev/null || true", shell=True)
                subprocess.run("sudo docker exec s1 tc qdisc del dev s1s0 root 2>/dev/null || true", shell=True)
                try:
                    if snap_idx in DEGRADED_ITERS:
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
                    print(f" [WARNING] Failed to change link properties: {e}")

            elif hindering == 'take down':
                try:
                    if snap_idx in DEGRADED_ITERS:
                        msg = f" [FAILURE] Snapshot {snap_idx}: Taking down link MG <-> ES (IP LINK DOWN)"
                        cmd1 = "sudo docker exec s1 ip link set s1s0 down"
                        cmd2 = "sudo docker exec s0 ip link set s0s1 down"
                    else:
                        msg = f" [RECOVERY] Snapshot {snap_idx}: Restoring link MG <-> ES (IP LINK UP)"
                        cmd1 = "sudo docker exec s1 ip link set s1s0 up"
                        cmd2 = "sudo docker exec s0 ip link set s0s1 up"

                    print(msg)
                    utils.append_event(run_root, msg)
                    subprocess.run(cmd1, shell=True, check=True)
                    subprocess.run(cmd2, shell=True, check=True)
                except Exception as e:
                    print(f" [WARNING] Falha ao alterar as propriedades do link: {e}")

            """
                Step: Log interface properties
            """
            link_properties = subprocess.run("sudo tc qdisc show", shell=True, check=True, capture_output=True, text=True)
            utils.append_event(run_root, f"SNAPSHOT_{snap_idx}: {link_properties}")

            """
                Step: Resolve service name
            """
            service = {
                '1': 'cdn-qoe', '2': 'llm', '3': 'treshold', '4': 'fwd', '5': 'ospf'
            }.get(algorithm, 'unknown')

            msg = " [WAIT] Waiting for ONOS telemetry (5s)..."
            print(msg)
            utils.append_event(run_root, msg)
            time.sleep(5)

            """
                Step: Send intents to deployer (if applicable)
            """
            if mode_cfg.get("use_deployer", False):
                for raw_ip in topo.client_ip_range:
                    clean_ip = raw_ip.split('/')[0].strip()
                    payload = {"intent": f"define intent q1: from endpoint('{clean_ip}') add service('{service}')"}

                    print(f"\n [SNAPSHOT {snap_idx}] Requesting {service} for {clean_ip}...")
                    try:
                        response = requests.post(base_url_deployer, json=payload, timeout=ROTATE_S)
                        if response.status_code in [200, 201]:
                            data = response.json()
                            ctrl_resps = data.get('controller_responses', {})
                            for ip, info in ctrl_resps.items():
                                flows = info.get('output', {}).get('responses', [])
                                print(f" [DEPLOYER] {len(flows)} flows installed by ONOS ({ip})")
                                for f in flows:
                                    f_id = f['location'].split('/')[-1]
                                    dpid = f['location'].split('/')[-2]
                                    print(f"    -> Flux {f_id} on Switch {dpid}")
                        else:
                            print(f" [ERROR] Deployer returned {response.status_code}")
                    except Exception as e:
                        print(f" [ERROR] Request error: {e}")

                # After deployer, wait the full rotation window
                print(f" [WAIT] Waiting {ROTATE_S}s for traffic window...")
                time.sleep(ROTATE_S)

            """
                Step: DEBUG — Quick connectivity probe before launching iperf
            """
            for client_name in topo.clients.keys():
                debug_iperf_connectivity(client_name, server_ip, port=5201)

            """
                Step: Launch iperf3 on every client
            """
            iperf_jobs = []
            for client_name in topo.clients.keys():
                out_json = iperf_dir / f"{client_name}%{snap_idx}.json"
                err_log  = iperf_dir / f"{client_name}%{snap_idx}.err" # stderr captured separately

                cmd = [
                    "sudo", "docker", "exec", client_name, "bash", "-lc",
                    f"iperf3 -c {server_ip} -p 5201 -t {ROTATE_S} -i 1 -J --connect-timeout 10000 --get-server-output"
                ]

                f_out = open(out_json, "w", encoding="utf-8")
                f_err = open(err_log,  "w", encoding="utf-8")
                proc = subprocess.Popen(cmd, stdout=f_out, stderr=f_err, text=True)
                iperf_jobs.append((proc, f_out, f_err, client_name))

            msg = get_network_summary(topo)
            print(msg)
            utils.append_event(run_root, msg)

            """
                Step: Wait for iperf3, validate JSON, log stderr
            """
            for proc, f_out, f_err, client_name in iperf_jobs:
                try:
                    proc.wait(timeout=ROTATE_S + 30)
                except subprocess.TimeoutExpired:
                    print(f" [WARNING] iperf timeout for {client_name} — killing process")
                    proc.kill()
                    proc.wait(timeout=5)
                finally:
                    for fh in (f_out, f_err):
                        try: fh.close()
                        except Exception: pass

                # Log stderr content (confirms "server busy", connection refused, etc.)
                err_log  = iperf_dir / f"{client_name}%{snap_idx}.err"
                err_content = err_log.read_text(encoding="utf-8").strip()
                if err_content:
                    print(f" [IPERF STDERR] {client_name} snap {snap_idx}: {err_content}")
                    utils.append_event(run_root, f" [IPERF STDERR] {client_name} snap {snap_idx}: {err_content}")

                # Validate JSON output
                out_json = iperf_dir / f"{client_name}%{snap_idx}.json"
                try:
                    with open(out_json, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if "end" not in data:
                        raise ValueError("Missing 'end' key — incomplete iperf3 output")
                    bps = data["end"]["sum_received"]["bits_per_second"]
                    print(f" [IPERF OK] {client_name} snap {snap_idx}: {bps/1e6:.1f} Mbit/s")
                    utils.append_event(run_root, f" [IPERF OK] {client_name} snap {snap_idx}: {bps/1e6:.1f} Mbit/s")
                except Exception as e:
                    print(f" [IPERF INVALID] {client_name} snap {snap_idx}: {e}")
                    utils.append_event(run_root, f" [IPERF INVALID] {client_name} snap {snap_idx}: {e}")

            time.sleep(2)

            """
                Step: OVS snapshot
            """
            utils.snapshot_ovs_state(
                switch_names=[sw.getNodeName() for sw in topo.switches.values()],
                outdir=ovs_dir,
                of_version="OpenFlow13",
                parse_csv=True,
                snapshot_idx=snap_idx,
            )

            """
                Step: Build iperf CSV for this snapshot
            """
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
