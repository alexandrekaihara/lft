# LFT KVM lab — reproducible VM runbook

Run the whole LFT/ONOS lab inside a single KVM virtual machine managed by
[Incus](https://linuxcontainers.org/incus/), so that every teammate gets an
identical environment and the shared testbed can be rebuilt from scratch in
minutes. This document reverse-engineers and formalizes the deployment that
runs in production on the lab server (`tupana`, VM `lft-vm`) — nothing here is
theoretical.

Target audience: **Linux hosts** (that is where KVM/Incus run). Teammates on
macOS/Windows do not run the lab locally; they use the shared instance over
WireGuard (§5). Everything else in this doc is distro-agnostic where possible:
the scripts auto-detect `apt` and `dnf`, and Incus itself is packaged for
Ubuntu/Debian/Fedora/Arch and derivates.

## 1. Architecture

```
 Linux host (Incus + WireGuard)
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
- For the shared-access part (§5): WireGuard.

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
| WireGuard | `wireguard-tools` | §5 |
| Python | 3.12 venv via [uv](https://docs.astral.sh/uv/) | pinned deps (`uv.lock`) when the branch carries it, `pip install -e .` otherwise |
| Images | `onosproject/onos:2.5.0`, `alexandremitsurukaihara/lst2.0:openvswitch`, locally built `lft-iperf:latest` | controller, switches, endpoints |

ONOS is started as `c1` with `--pid host` and its ports published
(REST/GUI 8181, karaf ssh 8101, NETCONF 830, JVM debug 5005, OpenFlow 6653),
matching the deployment the experiments were validated against.

## 5. WireGuard: make the VM a first-class tunnel peer

The robust way to let the whole team reach the lab is **not** per-port
forwarders on the host (they die with their process) but giving the VM its own
tunnel identity. Any WireGuard network works; the lab server runs a
hub-and-spoke `10.8.0.0/24` where the VM got `10.8.0.10`.

On the VM:

```bash
umask 077 && wg genkey | tee /etc/wireguard/privatekey | wg pubkey > /etc/wireguard/publickey
cat > /etc/wireguard/wg0.conf <<EOF
[Interface]
PrivateKey = $(cat /etc/wireguard/privatekey)
Address = <VM_TUNNEL_IP>/32

[Peer]
PublicKey = <HUB_PUBLIC_KEY>
Endpoint = <HUB_ENDPOINT>:51820
AllowedIPs = <TUNNEL_CIDR>      # e.g. 10.8.0.0/24 — only the tunnel, default route untouched
PersistentKeepalive = 25        # the VM sits behind the incus bridge NAT
EOF
systemctl enable --now wg-quick@wg0
```

On the hub, add the VM's public key as a peer with
`AllowedIPs = <VM_TUNNEL_IP>/32` (append to the config file **and** apply live
with `wg set`, so nobody drops), and every existing peer can already reach the
VM because they route the whole tunnel CIDR to the hub. No firewall inside the
VM means every service port is reachable from the tunnel — that is the point.

Real-world values used on the lab server: host `tupana` `10.8.0.8`, VM
`lft-vm` `10.8.0.10`, hub `tunnel.dwcorp.com.br:51820`.

## 6. Team access (shared instance)

With §5 in place, everyone on the tunnel reaches the VM directly:

| Port | Service |
|---|---|
| 8181 | ONOS REST / web UI |
| 8101 | ONOS karaf SSH (`onos`/`rocks`) |
| 830 | ONOS NETCONF |
| 5005 | ONOS JVM debug |
| 4180 | REIN console API |
| 22 | SSH into the VM (add your public key via `incus exec`) |

Root shell without SSH: `sudo incus exec lft-vm -- bash` on the host.

Client-side caveat: a peer only reaches `x.y.z.w` if its **own**
`AllowedIPs` includes it — use the full tunnel CIDR (e.g. `10.8.0.0/24`),
not single /32s, or you will hit "works for `.10`, not for `.8`" symptoms.

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
| WireGuard handshake but no traffic | client-side `AllowedIPs` too narrow (see §6) or hub peer missing the VM's `AllowedIPs` |
| ONOS ports closed from the tunnel | check `docker ps` publishes them (`-p 8181:8181 …`), then `wg show` inside the VM |
| socat/per-port forwards | don't — that approach was retired; use §5 |
