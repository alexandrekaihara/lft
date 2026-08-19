#!/bin/bash

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


# Start OVS
sudo /usr/share/openvswitch/scripts/ovs-ctl start
service start firewalld

# Wait for OVSDB socket to appear (up to 30s)
for i in $(seq 1 30); do
  if [ -S /var/run/openvswitch/db.sock ]; then
    echo "OVSDB socket ready"
    break
  fi
  sleep 1
done

# Start gNMI adapter in background
/usr/local/bin/ovs-gnmi-adapter \
  --ovsdb-socket=/var/run/openvswitch/db.sock \
  --gnmi-addr=0.0.0.0 \
  --gnmi-port=9339 \
  --tls-cert=/etc/ovs-gnmi-adapter/tls/server.crt \
  --tls-key=/etc/ovs-gnmi-adapter/tls/server.key \
  --latency-targets-file=/etc/ovs-gnmi-adapter/latency-targets.conf \
  &

# Open firewall port for gNMI
firewall-cmd --add-port=9339/tcp 2>/dev/null || true

# Start container and keep alive
tail -f /dev/null
