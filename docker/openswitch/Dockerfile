#
# Copyright (C) 2022 Alexandre Mitsuru Kaihara
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

# --- Stage 1: Build the Go adapter ---
FROM golang:1.22-bookworm AS adapter-builder
WORKDIR /build
COPY adapter/go.mod adapter/go.sum ./
RUN go mod download
COPY adapter/ ./
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o ovs-gnmi-adapter .

# --- Stage 2: Runtime (existing image + adapter binary) ---
FROM ubuntu:20.04

RUN apt update \
&& RUNLEVEL=1 apt install -y --no-install-recommends openvswitch-switch sudo net-tools iproute2 iputils-ping nano iptables tshark firewalld tcpdump

# Copy and start script
COPY onboot.sh /home
RUN chmod +x /home/onboot.sh

# Copy adapter binary from build stage
COPY --from=adapter-builder /build/ovs-gnmi-adapter /usr/local/bin/ovs-gnmi-adapter
RUN chmod +x /usr/local/bin/ovs-gnmi-adapter

# TLS certs directory (populated by generate_dev_certs.sh at build time, or mounted at runtime)
RUN mkdir -p /etc/ovs-gnmi-adapter/tls
COPY adapter/tls/certs/server.crt /etc/ovs-gnmi-adapter/tls/server.crt
COPY adapter/tls/certs/server.key /etc/ovs-gnmi-adapter/tls/server.key
COPY adapter/tls/certs/ca.crt /etc/ovs-gnmi-adapter/tls/ca.crt

CMD ["./home/onboot.sh"]

# For connecting via Open SSL
EXPOSE 22

# gNMI server
EXPOSE 9339
