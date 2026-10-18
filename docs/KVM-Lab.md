# LFT KVM lab — reproducible VM runbook

Run the whole LFT/ONOS lab inside a single KVM virtual machine managed by
[Incus](https://linuxcontainers.org/incus/), so that every teammate gets an
identical environment and the shared testbed can be rebuilt from scratch in
minutes. This document reverse-engineers and formalizes the deployment that
runs in production on the lab server (`tupana`, VM `lft-vm`) — nothing here is
theoretical.

Target audience: **Linux hosts** (that is where KVM/Incus run). Teammates on
macOS/Windows do not run the lab locally; they use the shared instance over
the network (§5). Everything else in this doc is distro-agnostic where possible:
the scripts auto-detect `apt` and `dnf`, and Incus itself is packaged for
Ubuntu/Debian/Fedora/Arch and derivates.

## 1. Architecture

```
 Linux host (Incus)
 └── lft-vm  ·  KVM virtual machine, Ubuntu noble
     ├── docker
     │   ├── c1            onosproject/onos:2.5.0   (--pid host, ports 8181/8101/830/5005/6653)
     │   ├── s0..sN        lst2.0:openvswitch       (OVS switches, one container each)
     │   ├── cl*, ds*      lft-iperf:latest         (iperf3 clients/servers, built from docker/lft-iperf)
     │   └── deployer/supervisor/profiler  (REIN)
     ├── openvswitch (host side, used by the topology drivers)
     └── /root/lft   ·  this repo, in a uv-managed venv (Python 3.12)
```

One VM contains the controller (ONOS), the data plane (OVS containers), the
traffic endpoints (iperf containers) and the experiment drivers (this repo).
The production instance runs with 6 vCPUs, 8 GiB RAM and a 60 GiB root disk,
which is comfortable for the 27-switch topologies.

## 2. Host requirements

- Linux with KVM: `ls -l /dev/kvm` must exist (and be usable by the incus user).
- [Incus](https://linuxcontainers.org/incus/docs/main/installing/) ≥ 6.x
  (the `images:ubuntu/noble` `disk-kvm` image is used for the VM).
- ~70 GiB free disk, ≥ 8 GiB RAM to spare.
### Distro support (Linux)

KVM itself is a mainline kernel feature — every Linux distro has it; you need
VT-x/AMD-V in the CPU and `/dev/kvm` on the host. What varies is only how you
install the stack:

| Distro family | KVM/QEMU | Incus |
|---|---|---|
| Debian / Ubuntu | in the archive (`qemu-kvm`) | [Zabbly apt repo](https://github.com/zabbly/incus) (recommended) — Debian 13+ also carries Incus in its own archive |
| Fedora | in the archive | official Fedora package (`dnf install incus`) |
| RHEL / CentOS Stream | in the archive | via [snap](https://snapcraft.io/incus) (`snap install incus`) |
| Arch | in the archive (`qemu-full`) | official repos (`pacman -S incus`) |

The scripts in this repo auto-detect `apt` and `dnf` (and pacman is trivial to
add) — they only wrap package names; the Incus, Docker and OVS layer is
identical everywhere.

## 3. Quickstart

From the repo root on the host:

```bash
# 1. create and start the VM (defaults: lft-vm, 6 CPUs, 8 GiB, 60 GiB)
sudo bash scripts/vm/create-lft-vm.sh

# 2. provision happens automatically inside the VM (docker, OVS, ONOS,
#    lft-iperf image, uv venv). Re-runnable:
sudo incus exec lft-vm -- bash /root/provision-vm.sh

# 3. validate
sudo incus exec lft-vm -- bash -c 'cd /root/lft && python3 scripts/vm/smoketest.py'
```

Both scripts are idempotent and parameterized via environment variables
(`VM_NAME`, `VM_CPUS`, `VM_MEM`, `VM_DISK`, `LFT_REPO`, …) — see the headers.

## 4. What provisioning installs (inside the VM)

| Piece | Value | Why |
|---|---|---|
| OS | Ubuntu noble, `disk-kvm` image | validated layout |
| Docker | `docker.io` (or `docker-ce`) + enabled | data plane + ONOS run as containers |
| Open vSwitch | `openvswitch-switch` + enabled | topology drivers call `ovs-*` on the VM |
| Python | 3.12 venv via [uv](https://docs.astral.sh/uv/) | pinned deps (`uv.lock`) when the branch carries it, `pip install -e .` otherwise |
| Images | `onosproject/onos:2.5.0`, `alexandremitsurukaihara/lst2.0:openvswitch`, locally built `lft-iperf:latest` | controller, switches, endpoints |

ONOS is started as `c1` with `--pid host` and its ports published
(REST/GUI 8181, karaf ssh 8101, NETCONF 830, JVM debug 5005, OpenFlow 6653),
matching the deployment the experiments were validated against.

## 5. Exposing ports from the VM

All lab services publish their ports on the VM's network interfaces (ONOS
publishes 8181/8101/830/5005/6653 via `docker run -p`, see §4). The VM gets
its address from the Incus bridge (`incusbr0`, e.g. `10.90.90.x`) and is
reachable from the host as-is. To open it up further, pick what fits the team:

| Scope | How |
|---|---|
| Host only | nothing to do — `incus exec` or the bridge IP |
| Others on the host LAN | an Incus **proxy device** (below) publishes a VM port on a host address |
| Selected teammates | SSH local forward from any machine with SSH access to the host: `ssh -L 8181:<VM_IP>:8181 user@host` |
| Whole team, standing access | the team's VPN/tunnel of choice — run it **inside the VM** and give the VM its own address (per-port relay scripts on the host are the classic "worked yesterday" failure: they die with their process) |

Incus proxy device — no firewall edits inside the VM, survives reboots:

```bash
incus config device add lft-vm onos-ui proxy \
  listen=tcp:0.0.0.0:8181 connect=tcp:<VM_IP>:8181
# remove again with: incus config device remove lft-vm onos-ui
```

## 6. Team access (shared instance)

With the VM reachable (§5), the services are:

| Port | Service |
|---|---|
| 8181 | ONOS REST / web UI |
| 8101 | ONOS karaf SSH (`onos`/`rocks`) |
| 830 | ONOS NETCONF |
| 5005 | ONOS JVM debug |
| 4180 | REIN console API |
| 22 | SSH into the VM (add public keys via `incus exec`) |

Root shell without SSH: `sudo incus exec lft-vm -- bash` on the host.

## 7. Running an experiment

Validated smoketest (legacy `iperf_experiment` layout — kept for reference, it
is what the production VM was validated with):

```bash
sudo incus exec lft-vm -- bash -c 'cd /root/lft && python3 scripts/vm/smoketest.py'
```

For the current reorganized tree use the CLI / `onos_topologies` entry points
(`python cli.py …`, `onos_topologies/create_n_run.py`) — the VM layout is
agnostic to which driver builds the topology.

## 8. Troubleshooting

| Symptom | Fix |
|---|---|
| `incus exec` hangs right after launch | the guest agent isn't up yet; wait ~1 min (`incus list` shows no IPv4 until then) |
| VM has no KVM acceleration | `ls -l /dev/kvm`; enable VT-x/AMD-V in BIOS; add your user to the `kvm` group |
| Port reachable from the host but not from outside it | expose it properly (§5) — proxy device on the host, or the team VPN running inside the VM |
| ONOS ports closed | check `docker ps` publishes them (`-p 8181:8181 …`) and that ONOS finished booting (~1 min) |
| per-port relay scripts (socat etc.) | avoid — they die with their process; use §5 |
