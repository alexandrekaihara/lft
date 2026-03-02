# Lightweight Fog Testbed (LFT) – iPerf Experiment Branch

## Description

This branch extends the **Lightweight Fog Testbed (LFT)** into a research environment for **Intent-Based Networking (IBN)**. This particular experiment involves a **Deployer** that receives, processes and applies **Nile intents** within a virtualized topology built with **ONOS** and **Open vSwitch (OVS)**.

The platform supports a  **iperf3-based experimental track** to compare five distinct routing paradigms under network stress (**degradation** or **link failure**):

- **CDN-QoE**: Algorithm for optimal path and server selection, considering real-time RTT and throughput.
- **LLM**: Routing using **Llama 3.1** (via **Ollama**) for decision-making.
- **Threshold**: (not defined yet).
- **Reactive Forwarding (fwd)**: Standard SDN shortest-path routing based on hop count.
- **OSPF (Legacy)**: Traditional link-state protocol running on **ONOS v1.5**.

---

## 1. Requirements

You need:

- (Recommended) Ubuntu Desktop 24.04 LTS
- Docker (with permission to run `sudo docker …`)
- Python 3 and `pip3`
- Git
- `tmux` for persistent runs over SSH

---

## 2. Installation & Image Build

To install the project you need to run:

```
pip3 install profissa_lft
```

In case of any missing dependency you can manually clone the repository and run the dependencies script:

```
git clone https://github.com/alexandrekaihara/lft
cd lft
git checkout dash-experiments
chmod +X dependencies.sh
./dependencies.sh
```

## 2.1 Build Docker Images

```
# ONOS 2.5 (Compatible with link-latency app)
cd docker/onos_v2.5 && sudo docker build -t onosproject/onos:2.5.0 .

# ONOS 1.5 (Compatible with OSPF)
sudo docker pull onosproject/onos:1.5

# OpenSwitch
cd docker/openswitch && sudo docker build -t alexandremitsurukaihara/lst2.0:openvswitch .

# Quagga Router
cd docker/quagga && sudo docker build -t quagga .

```
## 3. First Run

On the source root of the project run:

```
cd onos_topologies/iperf_experiment
python3 main.py
```

### 3.1 Customize topology

If you want to customize the topology, it's possible to do so by changing the data structures within iperf_experiment/constants.py.

### 3.2 Access ONOS user interface
ONOS provides an application called **ui2** for visualizing the topology and some platform features. After starting ONOS, you can access it in your browser at:

```text
http://localhost:8181/onos/ui/#/topo2
```

### 3.3 Access ONOS CLI
It's possible to
`ssh -p 8101 karaf@localhost`

## 4. Results

The experiment runs in a loop of **6 snapshots** (default: **10 minutes each**).

### Snapshot Schedule

- **Snapshots 1, 3, 4, and 6**: baseline / normal network state
- **Snapshots 2 and 5**: the selected **hindering** is applied to a link


### Output Directory

Results are stored in:

```text
results/iperf/run_YYYY-MM-DD_HH-MM-SS/
```
### Generated Files

At the end of the run, the script automatically generates unified CSV files:

- `iperf_flow_all.csv`: throughput, jitter and packet loss data
- `ping_flow_all.csv`: high-resolution RTT logs with timestamps

- `ovs_ports_all.csv`: per-port traffic, drops and errors
- `ovs_flows_all.csv`: flow rules, actions and counters

## 5. Cleaning up the environment

To stop and remove all containers on the host (including those from this experiment):

```bash
sudo docker rm -f $(sudo docker ps -aq) 2>/dev/null || true
sudo docker network prune -f
```

## 6. Troubleshooting
If you face any issue while running any LFT scrips:
1. Check if all dependencies are installed
2. Check if you are using the correct version of Ubuntu Desktop
3. Check if the containers are already instantiated on docker ```docker ps -a```. If so, then remove them by using ```docker system prune``` or forcefully stop them ```docker rm -f containerName```
4. Verify if the docker image that you are trying to instantiate with LFT exists on your local machine ```docker images``` or exists on [Docker Hub|https://hub.docker.com/].
5. Check if the image was built correctly. See docker folder for more information.
