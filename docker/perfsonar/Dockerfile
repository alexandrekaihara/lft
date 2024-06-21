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


FROM ubuntu:20.04

# Basic depencencies needed for network debugging inside a container
RUN apt update \
&&  RUNLEVEL=1 apt install -y --no-install-recommends sudo net-tools iproute2 iputils-ping iptables nano software-properties-common curl wget unzip iperf3

# Install perfsonar-testpoint
RUN apt install -y software-properties-common gpg-agent curl && \
        cd /etc/apt/sources.list.d/ && \
        curl -o perfsonar-release.list http://downloads.perfsonar.net/debian/perfsonar-release.list && \
        curl http://downloads.perfsonar.net/debian/perfsonar-official.gpg.key | tac | tac | apt-key add - && \
        apt update

COPY onboot.sh /

RUN chmod +x /onboot.sh

CMD ["./onboot.sh"] 

EXPOSE 22

