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


FROM ubuntu:22.04

RUN apt update \
&& DEBIAN_FRONTEND=noninteractive RUNLEVEL=1 apt install -y --no-install-recommends openvswitch-switch sudo net-tools iproute2 iputils-ping nano iptables software-properties-common wget unzip

RUN wget https://github.com/srsran/srsRAN_4G/archive/refs/heads/master.zip
RUN unzip master.zip && \
        mv srsRAN_4G-master srsRAN

RUN DEBIAN_FRONTEND=noninteractive apt-get install -y cmake \
	libfftw3-dev \
	libmbedtls-dev \
	libboost-program-options-dev \
	libconfig++-dev \
	libsctp-dev \
	libzmq3-dev \
	build-essential \
        gnuradio

RUN mkdir /srsRAN/build && \
    cd /srsRAN/build && \
    cmake ../ && make && make install && ldconfig && \
   ./srsran_install_configs.sh service

RUN mkdir /etc/srsRAN && \ 
    cp /srsRAN/srsue/ue.conf.example /etc/srsran/ue.conf && \
    cp /srsRAN/srsenb/enb.conf.example /etc/srsran/enb.conf && \
    cp /srsRAN/srsenb/rb.conf.example /etc/srsran/rb.conf && \
    cp /srsRAN/srsenb/rr.conf.example /etc/srsran/rr.conf && \
    cp /srsRAN/srsenb/sib.conf.example /etc/srsran/sib.conf && \
    cp /srsRAN/srsepc/epc.conf.example /etc/srsran/epc.conf && \
    cp /srsRAN/srsepc/user_db.csv.example /etc/srsran/user_db.csv

COPY onboot.sh /srsRAN/build/
COPY multiUE.py /srsRAN/build/

COPY onboot.sh /home
RUN chmod +x /home/onboot.sh
CMD ["./home/onboot.sh"]

# For conecting via Open SSL
EXPOSE 22

