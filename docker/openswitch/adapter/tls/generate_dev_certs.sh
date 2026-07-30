#!/bin/bash
set -e

CERT_DIR="$(dirname "$0")/certs"
mkdir -p "$CERT_DIR"

echo "Generating self-signed TLS certificate for dev gNMI server..."

openssl req -x509 -newkey rsa:2048 \
  -keyout "$CERT_DIR/server.key" \
  -out "$CERT_DIR/server.crt" \
  -days 365 -nodes \
  -subj "/CN=ovs-gnmi-adapter/O=profissa-dev"

cp "$CERT_DIR/server.crt" "$CERT_DIR/ca.crt"

chmod 600 "$CERT_DIR/server.key"

echo "Done. Certs in $CERT_DIR:"
ls -la "$CERT_DIR"
