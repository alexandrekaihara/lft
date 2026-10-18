#!/usr/bin/env bash
# Provision the LFT lab inside the VM (run as root in the guest).
# Idempotent: safe to re-run. Reconstructed from the production lft-vm.
#
#   provision-vm.sh [LFT_REPO]   # default https://github.com/UnB-COMNET/lft.git
set -euo pipefail

LFT_REPO="${1:-https://github.com/UnB-COMNET/lft.git}"
LFT_DIR="${LFT_DIR:-/root/lft}"
ONOS_IMAGE="${ONOS_IMAGE:-onosproject/onos:2.5.0}"
OVS_IMAGE="${OVS_IMAGE:-alexandremitsurukaihara/lst2.0:openvswitch}"

[[ $EUID -eq 0 ]] || { echo "run as root" >&2; exit 1; }

pkg_install() {
  if command -v apt-get >/dev/null; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -y
    apt-get install -y --no-install-recommends "$@"
  elif command -v dnf >/dev/null; then
    dnf install -y "$@"
  else
    echo "unsupported package manager (need apt or dnf)" >&2; exit 1
  fi
}

echo "==> base packages"
pkg_install docker.io openvswitch-switch wireguard-tools curl git ca-certificates \
  python3 python3-pip iperf3 tcpdump
# (on dnf distros the docker package is 'moby-engine' or 'docker-ce' from the
#  upstream repo; docker.io is the Ubuntu/Debian name — adjust to taste)

systemctl enable --now docker openvswitch-switch

if ! docker ps >/dev/null 2>&1; then
  echo "docker not usable by root?" >&2; exit 1
fi

echo "==> controller and switch images"
docker pull "$ONOS_IMAGE"
docker pull "$OVS_IMAGE"

echo "==> lft-iperf endpoint image (from this repo's docker/lft-iperf)"
docker build -t lft-iperf:latest /root/lft-iperf

echo "==> ONOS as container c1 (--pid host, like production)"
docker rm -f c1 2>/dev/null || true
docker run -d --name c1 --restart unless-stopped --pid host \
  -p 8181:8181 -p 8101:8101 -p 830:830 -p 5005:5005 -p 6653:6653 \
  "$ONOS_IMAGE"

echo "==> this repo + python env"
if [ ! -d "$LFT_DIR/.git" ]; then
  git clone "$LFT_REPO" "$LFT_DIR"
fi
cd "$LFT_DIR"

# uv when the branch carries the lockfile, pip otherwise
if command -v uv >/dev/null 2>&1 || [ -f pyproject.toml ]; then
  if ! command -v uv >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
  fi
  uv python install 3.12
  [ -f uv.lock ] && uv sync || uv pip install -e .
else
  python3 -m pip install -e .
fi

echo "==> provisioned. ONOS UI: http://<VM_IP>:8181 (karaf ssh 8101, netconf 830)"
