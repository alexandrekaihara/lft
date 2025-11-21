# Lightweight Fog Testbed (LFT) – Intent-CDN branch

## Description

This branch extends the Lightweight Fog Testbed (LFT) to run a **DASH experiment** using:

- **ONOS** as SDN controller
- **Open vSwitch (OVS)** as data plane
- **Neubot DASH server and clients** (`neubot/dash`, `neubot/dash-client`)

Additionally, this branch includes:

- A **continuous diagnostics loop** (optional) that runs DASH clients periodically and stores results under `datadir/run_*`
- A **Jupyter notebook** to decompress, parse, and visualize the collected session results

---

## 1. Requirements

You need:

- Docker (with permission to run `sudo docker …`)
- Python 3 and `pip3`
- Git
- (Optional) Jupyter Lab / Notebook for analysis
- (Recommended) `tmux` for persistent runs over SSH

---

## 2. Installation

### Clone this fork

```bash
git clone [https://github.com/artdelpi/lft-intent-cdn.git](https://github.com/artdelpi/lft-intent-cdn.git)
cd lft-intent-cdn
chmod +x dependencies.sh
./dependencies.sh
```

---

## 3. Docker image build (DASH server and client)

This branch provides Dockerfiles for the DASH server and client under `docker/`.

### 3.1 Build DASH server image

From the repository root:

```bash
cd docker/dash_server
sudo docker build -t neubot/dash:latest -f Dockerfile .
```

### 3.2 Build DASH client image

```bash
cd docker/dash_client
sudo docker build -t neubot/dash-client:latest -f Dockerfile .
```

You can verify the images were created:

```bash
sudo docker images
```

You should see something similar to:

```text
neubot/dash         latest
neubot/dash-client  latest
```

---

## 4. TLS certs and datadir

The DASH server in this branch expects:

1. **TLS certs** in:
   ```text
   onos_topologies/dash_topology/certs/
     cert.pem
     key.pem
   ```

2. A **writable data directory** in:
   ```text
   onos_topologies/dash_topology/datadir/
   ```

The default Neubot behavior saves files under `datadir/dash/YYYY/MM/DD/*.json.gz`. During continuous diagnostics, results are reorganized automatically (see Section 7).

---

## 5. Executing the DASH / ONOS / OVS topology (main entrypoint)

**Important:** The entrypoint is now `main.py`. You must run it instead of `dash_topology.py`.

From the repository root:

```bash
cd /path/to/lft-intent-cdn
sudo python3 onos_topologies/dash_topology/main.py
```

This will:
- Instantiate the ONOS controller container (`c1`)
- Instantiate the OVS switches (`s0`, `s1`, …)
- Instantiate the DASH server host (`ds1`)
- Instantiate DASH clients (`cl0`, `cl1`, …) (one per PoP by default)
- Connect everything using a PoP-based topology
- Register switches to ONOS

### 5.1 Validated interactive execution

The validated execution path uses the following answers:

```text
Do you want to configure the topology interactively (Hosts, QoS, etc.)? [y/N] n

[INFO] Initializing topology with the following parameters:
  - Hosts per PoP: 1
  - Server PoP: PoP-RS
  - Server IP: 192.168.0.1
  - Client start IP octet: 192.168.0.2

Do you want the controller to discover all hosts? [y/N] y
Run quick tests (ping/curl)? [y/N] n
Run QoS diagnostics (tc qdisc + ping RTT)? [y/N] n
```

At the end, `main.py` will ask whether to start continuous diagnostics:

```text
Run continuous DASH diagnostics every 10 minutes? [y/N]
```

If **y**, the loop starts and saves results into `datadir/` (see next section).

## 6. Running with tmux (RECOMMENDED over SSH)

If you want the experiment to keep running even after closing the SSH session, use `tmux`.

### 6.1 Create a tmux session
From the repo root:

```bash
tmux new -s dashloop
```

Inside tmux, run the experiment:

```bash
sudo python3 onos_topologies/dash_topology/main.py
```

### 6.2 Detach without stopping
Press:
`Ctrl + b`, then `d`

Now you can close SSH and the loop keeps running in the VM.

### 6.3 Reattach later

```bash
tmux attach -t dashloop
```

### 6.4 Stop the session
First reattach (if needed), stop the Python program with `Ctrl + C`, then kill tmux:

```bash
tmux kill-session -t dashloop
```

---

## 7. Continuous DASH diagnostics (optional)

If you enable continuous diagnostics in `main.py`, the script will:

1. Create a unique run directory on the host:
   ```text
   onos_topologies/dash_topology/datadir/
     run_YYYY-MM-DD_HH-MM-SS/
       meta.json
       iter_0000/
         clients/
           cl0.json.gz
           cl1.json.gz
           ...
       iter_0001/
         clients/
           ...
   ```

2. Every **10 minutes**, each client runs `dash-client` once.
3. The newest `.json.gz` created by Neubot is moved from the default folder (`datadir/dash/YYYY/MM/DD/`) into the iteration folder shown above.
4. `meta.json` records run metadata such as start timestamp, configuration, number of clients, and interval.

To stop the loop, press `Ctrl+C` in the terminal running `main.py`.

---

## 8. Quick manual tests (optional)

You can still run these at any time:

### 8.1 Test the DASH negotiation endpoint
From the host:

```bash
docker exec cl0 bash -lc "curl -v --max-time 5 [http://192.168.0.1/negotiate/dash](http://192.168.0.1/negotiate/dash)"
```

### 8.2 Run the DASH client binary inside a single client

```bash
sudo docker exec cl0 bash -lc "/usr/local/bin/dash-client -y -hostname 192.168.0.1 -scheme http"
```

---

## 9. Jupyter analysis notebook

A notebook is provided to decompress, parse, and generate charts for the latest run.

**Location:**
`onos_topologies/dash_topology/notebooks/dash_analysis.ipynb`

### 9.1 Running Jupyter Lab

From inside `dash_topology/notebooks`:

```bash
cd onos_topologies/dash_topology/notebooks
jupyter lab --no-browser
```

If you need a fixed port (depending on your Jupyter version):

```bash
jupyter lab --no-browser --ServerApp.port=8888
# or
jupyter lab --no-browser --port=8888
```

Open the URL printed in the terminal (usually contains a token).

### 9.2 What the notebook does

The notebook:
1. Finds the latest `datadir/run_*/` directory.
2. Loads all files under each `iter_xxxx/clients/*.json.gz`.
3. Builds a DataFrame with per-client per-iteration stats (elapsed, received, rate, etc.).
4. Generates:
   - Evolution plots across rounds
   - Heatmaps per client/round
   - Throughput estimates from received / elapsed

This gives a fast way to compare network behavior across iterations and clients.

---

## 10. Results

Below are examples of the visualizations generated by the Jupyter notebook after running the script for 5 hours straight.

<div align="center"> <h3>Elapsed Time Heatmap</h3> <img src="results/dash_analysis//hmap_elapsed.png" alt="Heatmap of elapsed time per client/round" width="80%"> <p><em>Figure 1: Heatmap showing elapsed time variation across different clients and rounds.</em></p> </div>

<div align="center"> <h3>Average Elapsed Time Evolution</h3> <img src="results/dash_analysis//avg_elapsed.png" alt="Evolution of average elapsed time per round" width="60%"> <p><em>Figure 2: Trend of the average elapsed time over experimental rounds.</em></p> </div>

---

## 11. Cleaning up the environment

To stop and remove all containers on the host (including those from this experiment):

```bash
sudo docker rm -f $(sudo docker ps -aq) 2>/dev/null || true
sudo docker network prune -f
```
