#!/usr/bin/env bash
# Create the LFT lab VM on a Linux host with Incus.
#
# Reconstructed from the production instance (lft-vm on tupana): Ubuntu noble
# disk-kvm image, 6 vCPUs, 8 GiB RAM, 60 GiB root disk, autostart with the
# host, then provisioning is pushed and executed inside the guest.
#
# Override with env vars:
#   VM_NAME=lft-vm  VM_CPUS=6  VM_MEM=8GiB  VM_DISK=60GiB
#   UBUNTU_RELEASE=noble  LFT_REPO=<git URL of this repo>
set -euo pipefail

VM_NAME="${VM_NAME:-lft-vm}"
VM_CPUS="${VM_CPUS:-6}"
VM_MEM="${VM_MEM:-8GiB}"
VM_DISK="${VM_DISK:-60GiB}"
UBUNTU_RELEASE="${UBUNTU_RELEASE:-noble}"
LFT_REPO="${LFT_REPO:-https://github.com/UnB-COMNET/lft.git}"

[[ $EUID -eq 0 ]] || { echo "run with sudo" >&2; exit 1; }
command -v incus >/dev/null || { echo "incus not installed — https://linuxcontainers.org/incus/docs/main/installing/" >&2; exit 1; }
[[ -e /dev/kvm ]] || echo "WARNING: /dev/kvm missing — the VM will run without acceleration" >&2

if incus info "$VM_NAME" >/dev/null 2>&1; then
  echo "VM $VM_NAME already exists; state: $(incus list "$VM_NAME" --format csv -c s)"
  exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> launching $VM_NAME ($UBUNTU_RELEASE, $VM_CPUS cpus, $VM_MEM, $VM_DISK)"
incus init "images:ubuntu/$UBUNTU_RELEASE" "$VM_NAME" --vm \
  -c limits.cpu="$VM_CPUS" -c limits.memory="$VM_MEM" \
  -d root,size="$VM_DISK"
incus config set "$VM_NAME" boot.autostart=true   # survive host reboots

echo "==> starting (first boot takes ~1 min until the agent answers)"
incus start "$VM_NAME"
until incus exec "$VM_NAME" -- true 2>/dev/null; do sleep 5; done

echo "==> pushing and running the in-VM provisioner"
incus file push --recursive "$SCRIPT_DIR/../../docker/lft-iperf" "$VM_NAME"/root/lft-iperf
incus file push "$SCRIPT_DIR/provision-vm.sh" "$VM_NAME"/root/provision-vm.sh
incus exec "$VM_NAME" -- bash "/root/provision-vm.sh" "$LFT_REPO"

incus list "$VM_NAME"
echo
echo "Done. Next: expose the ports the team needs (docs/KVM-Lab.md §5) and"
echo "validate with scripts/vm/smoketest.py (§7)."
