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

RUN apt update \
&&  RUNLEVEL=1 apt install -y --no-install-recommends sudo net-tools iproute2 iputils-ping python3 python3-pip iptables nano\
&& python3 -m pip install --upgrade pip \
&& pip3 install ryu eventlet==0.30.2 pandas \
&& apt-get -o Dpkg::Options::="--force-confmiss" install --reinstall netbase

COPY controller.py /home

COPY onboot.sh /home
RUN chmod +x /home/onboot.sh
CMD ["./home/onboot.sh"]

# For conecting via Open SSL
EXPOSE 22

