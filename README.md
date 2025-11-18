# Lightweight Fog Testbed (LFT) – Intent-CDN branch

## Description

This branch extends the Lightweight Fog Testbed (LFT) to run a **DASH experiment** using:

- **ONOS** as SDN controller  
- **Open vSwitch (OVS)** as data plane  
- **Neubot DASH server and clients** (`neubot/dash`, `neubot/dash-client`)  

---

## 1. Requirements

You need:

- Docker (with permission to run `sudo docker …`)
- Python 3 and `pip3`
- Git

---

## 2. Installation

You can use the Python package or work directly from this fork.

### Option A – Install package (generic LFT)

    pip3 install profissa_lft

### Option B – Clone this fork (recommended for this branch)

    git clone https://github.com/artdelpi/lft-intent-cdn.git
    cd lft-intent-cdn
    chmod +x dependencies.sh
    ./dependencies.sh

---

## 3. Docker image build (DASH server and client)

This branch provides Dockerfiles for the DASH server and client under `docker/`.

### 3.1 Build DASH server image

From the repo root:

    cd docker/dash_server
    sudo docker build -t neubot/dash:latest -f Dockerfile .

### 3.2 Build DASH client image

    cd docker/dash_client
    sudo docker build -t neubot/dash-client:latest -f Dockerfile .

You can verify:

    sudo docker images

You should see something similar to:

- `neubot/dash          latest`
- `neubot/dash-client   latest`

---

## 4. TLS certs and datadir

The DASH server in this branch expects:

- TLS certs in `onos_topologies/certs/`  
  - `onos_topologies/certs/cert.pem`  
  - `onos_topologies/certs/key.pem`
- A writable data directory in `onos_topologies/datadir/` for storing DASH results (`-datadir`).

---

## 5. Executing the DASH / ONOS / OVS topology

From the repository root:

    cd /path/to/lft-intent-cdn
    sudo python3 onos_topologies/dash_topology.py

This will:

- Instantiate the **ONOS** controller container  
- Instantiate the **OVS** switches (e.g. `s0`, `s1`, `s22`, …)  
- Instantiate **DASH server** host `ds1`  
- Instantiate **DASH clients** `cl0`, `cl1`, …  
- Connect them using a PoP-based topology and register switches to ONOS  

You can check running containers:

    sudo docker ps

You should see, among others:

- `c1` (ONOS controller)  
- `sX` (switches)  
- `ds1` (DASH server)  
- `cl0`, `cl1`, … (DASH clients)

---

## 6. Quick tests

Below are minimal commands to verify that the experiment is working.

### 6.1 Test the DASH negotiation endpoint

From the host, targeting client `cl0`:

    docker exec cl0 bash -lc "curl -v --max-time 5 http://192.168.0.1/negotiate/dash"

You should receive an HTTP 200 response with a JSON body containing DASH parameters and authorization.

### 6.2 Run the DASH client binary inside `cl0`

    sudo docker exec cl0 bash -lc "/usr/local/bin/dash-client -y -hostname 192.168.0.1 -scheme http"

The client will:

- Contact `/negotiate/dash`
- Download DASH chunks from the server
- Print JSON with metrics per iteration (rate, elapsed, received, etc.)

### 6.3 Sniff HTTP traffic on the switch (port 80 only)

Assuming a Linux network namespace `s22` and veth interface `s22ds1` (switch ↔ `ds1`):

    sudo ip netns exec s22 tcpdump -i s22ds1 -n -e 'port 80'

In another terminal, you can re-run the negotiation or client commands above to observe packets.

---

## 7. Cleaning up the environment

To stop and remove **all** containers on the host (including those from this experiment):

    sudo docker rm -f $(sudo docker ps -aq) 2>/dev/null || true


