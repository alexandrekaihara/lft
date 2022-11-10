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


# Start container and keep alive
chmod +x /TCPDUMP_and_CICFlowMeter-master/CICFlowMeters/CICFlowMeter-4.0/bin/CICFlowMeter
chmod +x /TCPDUMP_and_CICFlowMeter-master/convert_pcap_csv.sh
chmod +x /TCPDUMP_and_CICFlowMeter-master/capture_interface_pcap.sh
sudo /usr/share/openvswitch/scripts/ovs-ctl start
tail -f /dev/null