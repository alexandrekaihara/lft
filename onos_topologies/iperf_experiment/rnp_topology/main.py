import os, sys, subprocess, random, time, json, requests, csv

from pathlib import Path

project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

from constants import CONFIG_RNP
from onos_topologies.dash_topology.dash_topology import DashTopology
from onos_topologies.dash_topology import utils


MODES = {
    '1': {"name": "cdn-qoe",  "onos": "2.5.0", "disable_fwd": True,  "apps": "proxyarp"},
    '2': {"name": "llm",      "onos": "2.5.0", "disable_fwd": True,  "apps": "proxyarp"},
    '3': {"name": "treshold", "onos": "2.5.0", "disable_fwd": True,  "apps": "proxyarp"},
    '4': {"name": "fwd",      "onos": "2.5.0", "disable_fwd": False, "apps": ""},
    '5': {"name": "ospf",     "onos": "1.6",   "disable_fwd": True,  "apps": "proxyarp"}
}


# Algoritmo que escolhe um int aleatório entre 0 e len-1 do POPS, e retorna um POP que receberá um cliente ou servidor
ADJACENCY_MATRIX = CONFIG_RNP["adjacency_matrix"]
POPS = CONFIG_RNP["pops"]
base_url_deployer = "http://127.0.0.1:5000/deploy"

# Escolhe aleatoriamente três POP para receber um cliente
for i in range(3):
    # Pega um índice aleatório de algum pop (0 a 29)
    pop_index = random.randint(0, len(POPS)-1)
    POPS[pop_index][1] += 1 # bota o cliente num pop aleatóiro

# Mesma coisa pra 10 servidores
for i in range(10):
    pop_index = random.randint(0, len(POPS)-1)
    POPS[pop_index][2] += 1 

# Agora, a cada execução, teremos servidores e clientes em POPS aleatórios

def _iperf_json_to_csv(json_path, csv_path) -> bool:
    """Converts an iperf3 JSON file (even if incomplete) to a per-interval CSV."""
    try:
        text = json_path.read_text(encoding="utf-8").strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Patch incomplete JSON: strip trailing comma/whitespace and close arrays
            text = text.rstrip().rstrip(',')
            if '"intervals"' in text:
                text += ']}'
            data = json.loads(text)

        intervals = data.get("intervals", [])
        if not intervals:
            return False

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "t_start", "t_end", "bytes", "bits_per_second", "retransmits"
            ])
            writer.writeheader()
            for iv in intervals:
                s = iv.get("sum", {})
                writer.writerow({
                    "t_start":         round(s.get("start", 0), 3),
                    "t_end":           round(s.get("end", 0), 3),
                    "bytes":           s.get("bytes", 0),
                    "bits_per_second": round(s.get("bits_per_second", 0), 2),
                    "retransmits":     s.get("retransmits", ""),
                })
        return True
    except Exception as e:
        print(f" [WARN] Could not parse {json_path.name}: {e}")
        return False


def main():
    algorithm = ''
    while algorithm not in {'1', '2', '3', '4', '5'}:
        algorithm = input(
            "Choose a number for the topology mode: "
            "\n[1] - cdn-qoe\n[2] - LLM\n[3] - Treshold\n[4] - fwd\n[5] - ospf\n"
        ).strip().lower()

    mode_cfg = MODES[algorithm]
    service  = mode_cfg["name"]


    # Cria diretorio de resultados igual ao diamond_topology
    results_root = project_root / "results" / "iperf"
    results_root.mkdir(parents=True, exist_ok=True)

    custom_name = (input("\nWould you like to add a custom name to the results directory? [y/N]\n").strip().lower() == "y")
    run_name = input("Please type in the name: ").strip().lower() if custom_name else None

    run_root = results_root / run_name if run_name else results_root / f"run_{time.strftime('%Y-%m-%d_%H-%M-%S')}"
    run_root.mkdir(parents=True, exist_ok=True)
    os.environ["LFT_RESULTS"] = str(run_root)

    iperf_dir = run_root / "iperf"
    iperf_dir.mkdir(parents=True, exist_ok=True)

    meta = {"algorithm": algorithm, "mode": mode_cfg["name"], "start_ts": int(time.time())}
    (run_root / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    utils.append_event(run_root, f"RUN_START {time.strftime('%Y%m%d-%H%M%S')}")

    try:
        utils.cleanup()

        onos_tag = f"onosproject/onos:{mode_cfg['onos']}"
        topo = DashTopology(config=CONFIG_RNP, results_dir=project_root / "results", iperf=True, onos_version=onos_tag)
        topo.run(run_discovery=True, disable_fwd=mode_cfg["disable_fwd"])
        c1 = topo.controller

        if mode_cfg["apps"]:
            print(f" [SETUP] Activating extra apps: {mode_cfg['apps']}")
            c1.activateONOSApps(server_ip=topo.onos_ip,
                                command=f"app activate org.onosproject.{mode_cfg['apps']}")

        if algorithm != '5':
            print(" [SETUP] Telemetry -> Real-Time Mode")
            comp = "com.maojianwei.link.quality.measurement.impl.MaoLinkQualityManager"
            karaf = "/home/onos/apache-karaf-4.2.14/bin/client -u karaf -p karaf"
            cmd_str = f"cfg set {comp} latencyAverageSize 1; cfg set {comp} probeInterval 500; cfg set {comp} calculateInterval 500"
            subprocess.run(f"echo '{cmd_str}' | sudo docker exec -i c1 {karaf}",
                        shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            print(" [SETUP] Telemetry skipped (not available on ONOS 1.6 / OSPF mode)")

        print("\n[DONE] Topology is up and running.")
        if algorithm == '1':
            print("\n [SETUP] Start the deployer and supervisor manually in separate terminals:")
            print("  deployer:   sudo docker run --rm -it --network host -v /var/run/docker.sock:/var/run/docker.sock --name deployer deployer")
            print("  supervisor: sudo docker run --rm -it --network host -v /var/run/docker.sock:/var/run/docker.sock --name supervisor supervisor")
            utils.sleep_countdown(30)


        procs = []
        out_files = []

        # Envia intent pra cada cliente
        if mode_cfg["name"] == "cdn-qoe":
            client_to_server = {}  # {client_ip: server_ip}
            for raw_ip in topo.client_ip_range:
                clean_ip = raw_ip.split('/')[0].strip()
                deployer_service = "cdn-qoe" if service == "treshold" else service
                payload = {"intent": f"define intent q1: from endpoint('{clean_ip}') add service('{deployer_service}')"}
                print(f"\n [SNAPSHOT 1] Sending intent for {clean_ip}...")
                try:
                    response = requests.post(base_url_deployer, json=payload, timeout=30)
                    if response.status_code in [200, 201]:
                        data = response.json()
                        srv_ip = data.get('server_ip')
                        if srv_ip:
                            client_to_server[clean_ip] = srv_ip
                            print(f" [DEPLOYER] client {clean_ip} -> server {srv_ip}")
                        for ip, info in data.get('controller_responses', {}).items():
                            flows = info.get('output', {}).get('responses', [])
                            print(f" [DEPLOYER] {len(flows)} flows installed by ONOS ({ip})")
                    else:
                        print(f" [ERROR] Deployer returned {response.status_code}")
                except Exception as e:
                    print(f" [ERROR] Request error: {e}")

            # Uma porta por cliente em cada servidor (5201, 5202, ...)
            from collections import Counter
            server_client_count = Counter(client_to_server.values())
            server_ports = {
                srv_ip: list(range(5201, 5201 + count))
                for srv_ip, count in server_client_count.items()
            }
            server_keys = list(topo.servers.keys())

            print(" [SETUP] Starting iperf3 servers...")
            for srv_ip, ports in server_ports.items():
                srv_name = server_keys[topo.server_ip_range.index(srv_ip)]
                for port in ports:
                    subprocess.run(
                        f"docker exec -d {srv_name} bash -lc 'iperf3 -s -p {port}'",
                        shell=True
                    )
                    print(f" [SERVER] {srv_name} ({srv_ip}) listening on :{port}")
            time.sleep(2)

            print(f" [TEST] Running iperf3 tests concurrently, staggered by 3s...")
            server_port_iter = {srv_ip: iter(ports) for srv_ip, ports in server_ports.items()}
            procs = []
            out_files = []
            for cli_idx, client_name in enumerate(topo.clients):
                client_ip = topo.client_ip_range[cli_idx].split('/')[0].strip()
                assigned_server = client_to_server.get(client_ip)
                if not assigned_server:
                    print(f" [WARN] No server assigned for {client_name} ({client_ip}), skipping.")
                    continue
                port = next(server_port_iter[assigned_server])
                safe_ip = assigned_server.replace(".", "-")
                out_json = iperf_dir / f"{client_name}_{safe_ip}_p{port}.json"
                print(f" [IPERF] {client_name} ({client_ip}) -> {assigned_server}:{port}")
                f_out = open(out_json, "w", encoding="utf-8")
                p = subprocess.Popen(
                    ["sudo", "docker", "exec", client_name, "iperf3",
                     "-c", assigned_server, "-p", str(port),
                     "--connect-timeout", "3000", "-b", "35M", "-t", "200",
                     "--forceflush", "-J"],
                    stdout=f_out, stderr=subprocess.STDOUT, text=True
                )
                procs.append((p, client_name))
                out_files.append(f_out)
                if cli_idx < len(topo.clients) - 1:
                    time.sleep(3)

        # demais modos: cada cliente usa um servidor aleatório
        else:
            print(f" [TEST] Running iperf3 tests for all clients with random servers...")
            for client_name in topo.clients:
                server_ip = random.choice(topo.server_ip_range)
                clean_server_ip = server_ip.split('/')[0].strip()
                safe_ip = server_ip.replace("/", "_").replace(".", "-")
                out_json = iperf_dir / f"{client_name}_{safe_ip}.json"
                with open(out_json, "w", encoding="utf-8") as f_out:
                    try:
                        subprocess.run(
                            ["sudo", "docker", "exec", client_name, "iperf3",
                             "-c", clean_server_ip, "--connect-timeout", "3000", "-J"],
                            stdout=f_out, stderr=subprocess.STDOUT, text=True,
                            timeout=20
                        )
                    except subprocess.TimeoutExpired:
                        f_out.write('{"error": "subprocess timeout"}')
                    time.sleep(0.5)
        
        time.sleep(600) # deixa rodando por 3 min

        for (p, cname), f_out in zip(procs, out_files):
            p.terminate()
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
            f_out.close()
            print(f" [IPERF] {cname} stopped.")

        utils.append_event(run_root, f"RUN_END {time.strftime('%Y%m%d-%H%M%S')}")
        print(f"\n [RESULTS] Run saved to: {run_root}")

    except KeyboardInterrupt:
        print("[CONTINUOUS] Stop requested.")

    finally:
        utils.append_event(run_root, f"CONTINUOUS_STOP {int(time.time())}")

        utils.merge_all_snapshot_csvs(
            run_root=Path(run_root),
            out_csv_name="packet_flow_all.csv",
            delete_inputs=False,
        )

        utils.merge_all_snapshot_ovs_csvs(
            run_root=Path(run_root),
            delete_inputs=False,
        )

        for json_file in sorted(iperf_dir.glob("*.json")):
            csv_file = json_file.with_suffix(".csv")
            ok = _iperf_json_to_csv(json_file, csv_file)
            print(f" [IPERF] {'OK' if ok else 'FAIL'} {json_file.name} → {csv_file.name}")

        try:
            utils.cleanup()
        except Exception:
            pass

    return
    
if __name__ == "__main__":
    main()