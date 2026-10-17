#!/usr/bin/env bash
# Temporarily exposes lft-vm's service ports to everyone on the WireGuard
# tunnel, by opening a scoped ufw rule per port and forwarding it with socat
# (wg0 tunnel IP -> the VM's address on incusbr0). Meant for short-lived,
# supervised access during development/debugging, not as a standing service:
# nothing here is installed as a systemd unit, and `down` removes every rule
# and process it created.
#
# Usage:
#   sudo scripts/wg-vm-tunnel.sh up
#   sudo scripts/wg-vm-tunnel.sh down
set -euo pipefail

WG_IP="${WG_IP:-10.8.0.8}"
VM_IP="${VM_IP:-10.90.90.67}"
PID_FILE="${PID_FILE:-/tmp/wg-vm-tunnel.pids}"

# port -> description (also used as the ufw rule comment)
declare -A PORTS=(
  [4180]="REIN console"
  [5005]="ONOS debug"
  [830]="ONOS netconf"
  [8101]="ONOS karaf ssh"
  [8181]="ONOS REST/GUI"
)

usage() { echo "usage: $0 {up|down}" >&2; exit 1; }
require_root() { [[ $EUID -eq 0 ]] || { echo "must run as root (sudo)" >&2; exit 1; }; }

up() {
  require_root
  : > "$PID_FILE"
  for port in "${!PORTS[@]}"; do
    ufw allow in on wg0 to any port "$port" proto tcp comment "${PORTS[$port]} - temp tunnel access"
    socat TCP-LISTEN:"$port",bind="$WG_IP",fork,reuseaddr TCP:"$VM_IP":"$port" &
    echo "$!" >> "$PID_FILE"
  done
  echo "up: forwarding ${!PORTS[*]} from $WG_IP to $VM_IP (pids in $PID_FILE)"
}

down() {
  require_root
  if [[ -f "$PID_FILE" ]]; then
    while read -r pid; do
      kill "$pid" 2>/dev/null || true
    done < "$PID_FILE"
    rm -f "$PID_FILE"
  fi
  for port in "${!PORTS[@]}"; do
    ufw delete allow in on wg0 to any port "$port" proto tcp 2>/dev/null || true
  done
  echo "down: tunnel forwarding and ufw rules removed"
}

case "${1:-}" in
  up) up ;;
  down) down ;;
  *) usage ;;
esac
