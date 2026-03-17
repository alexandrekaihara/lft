import sys, subprocess
from constants import CONFIG
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from onos_topologies.dash_topology.dash_topology import DashTopology
from onos_topologies.dash_topology import utils


MODES = {
    '1': {"name": "cdn-qoe",  "onos": "2.5.0", "disable_fwd": True,  "apps": "proxyarp"},
    '2': {"name": "llm",      "onos": "2.5.0", "disable_fwd": True,  "apps": "proxyarp"},
    '3': {"name": "treshold", "onos": "2.5.0", "disable_fwd": True,  "apps": "proxyarp"},
    '4': {"name": "fwd",      "onos": "2.5.0", "disable_fwd": False, "apps": ""},
    '5': {"name": "ospf",     "onos": "1.6",   "disable_fwd": True,  "apps": "proxyarp"}
}


if __name__ == "__main__":
    algorithm = ''
    while algorithm not in {'1', '2', '3', '4', '5'}:
        algorithm = input(
            "Choose a number for the topology mode: "
            "\n[1] - cdn-qoe\n[2] - LLM\n[3] - Treshold\n[4] - fwd\n[5] - ospf\n"
        ).strip().lower()

    mode_cfg = MODES[algorithm]

    utils.cleanup()

    onos_tag = f"onosproject/onos:{mode_cfg['onos']}"
    topo = DashTopology(config=CONFIG, results_dir=project_root / "results", iperf=True, onos_version=onos_tag)
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
        print("\n[NEXT] Run the deployer:")
        print("  cmd: sudo docker run --rm -it --network host -v /var/run/docker.sock:/var/run/docker.sock --name deployer deployer")
