#!/bin/bash
#
# Manual integration test script for the OVS-gNMI adapter.
# Requires: gnmic CLI (https://github.com/openconfig/gnmic) installed on the host.
#
# Usage:
#   ./test_gnmi.sh <container-name> [gnmic-flags]
#
# Example:
#   ./test_gnmi.sh ovs-test
#   ./test_gnmi.sh ovs-test --tls-ca /path/to/ca.crt
#
# Prerequisites:
#   1. Build and start the openswitch container:
#      cd docker/openswitch && docker build -t ovs-gnmi .
#      docker run -d --name ovs-test -p 9339:9339 ovs-gnmi
#   2. Create a bridge and port inside the container:
#      docker exec ovs-test ovs-vsctl add-br br0
#      docker exec ovs-test ovs-vsctl add-port br0 eth0
#   3. Install gnmic on the host:
#      curl -sL https://github.com/openconfig/gnmic/releases/latest/download/gnmic_0.36.0_linux_x86_64.tar.gz | tar xz -C /usr/local/bin
#

set -e

CONTAINER="${1:?Usage: $0 <container-name> [gnmic-flags]}"
shift
GNMIC_FLAGS="$@"

ADDR="localhost:9339"
CERT_DIR="$(dirname "$0")/tls/certs"

if [ ! -f "$CERT_DIR/server.crt" ]; then
    echo "Generating dev certs..."
    "$(dirname "$0")/tls/generate_dev_certs.sh"
fi

GNMIC_ARGS="-a $ADDR --tls-cert $CERT_DIR/server.crt --tls-key $CERT_DIR/server.key --skip-verify"
if [ -n "$GNMIC_FLAGS" ]; then
    GNMIC_ARGS="$GNMIC_ARGS $GNMIC_FLAGS"
fi

echo "=== 1. Capabilities ==="
gnmic $GNMIC_ARGS capabilities

echo ""
echo "=== 2. Get: interface oper-status ==="
gnmic $GNMIC_ARGS get \
  --path /interfaces/interface[name=br0]/state/oper-status

echo ""
echo "=== 3. Get: interface admin-status ==="
gnmic $GNMIC_ARGS get \
  --path /interfaces/interface[name=br0]/state/admin-status

echo ""
echo "=== 4. Get: all counters for eth0 ==="
gnmic $GNMIC_ARGS get \
  --path /interfaces/interface[name=eth0]/state/counters

echo ""
echo "=== 5. Get: specific counter (in-octets) ==="
gnmic $GNMIC_ARGS get \
  --path /interfaces/interface[name=eth0]/state/counters/in-octets

echo ""
echo "=== 6. Get: all interfaces (wildcard) ==="
gnmic $GNMIC_ARGS get \
  --path /interfaces/interface

echo ""
echo "=== 7. Subscribe: ON_CHANGE counters (10s) ==="
echo "    (Trigger a change in another terminal: docker exec $CONTAINER ovs-vsctl set Interface eth0 admin-state=down)"
timeout 10 gnmic $GNMIC_ARGS subscribe \
  --path /interfaces/interface[name=eth0]/state/oper-status \
  --mode on-change || true

echo ""
echo "=== 8. Subscribe: SAMPLE counters (3 intervals of 2s) ==="
timeout 7 gnmic $GNMIC_ARGS subscribe \
  --path /interfaces/interface[name=eth0]/state/counters/in-octets \
  --mode sample --sample-interval 2s || true

echo ""
echo "=== 9. Get: custom rate paths (if available) ==="
gnmic $GNMIC_ARGS get \
  --path /org-lft/interfaces/interface[name=eth0]/state/rate || echo "    (rate paths may be empty until enough samples are collected)"

echo ""
echo "=== Done ==="
