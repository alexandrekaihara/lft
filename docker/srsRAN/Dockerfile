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

# Install basic dependencies
RUN apt update && apt upgrade -y \
&&  RUNLEVEL=1 apt install -y --no-install-recommends sudo net-tools iproute2 iputils-ping iptables nano software-properties-common wget unzip

# Install UHD Driver
RUN apt install -y --no-install-recommends git cmake git libboost-all-dev libusb-1.0-0-dev libudev-dev libncurses5-dev build-essential python3-pip dpdk dpdk-dev && \
        pip3 install mako && \
        git clone https://github.com/EttusResearch/uhd.git && \
        cd uhd && \
        git checkout v3.15.0.0 && \
        cd host && mkdir build && cd build && \
        cmake ../ && make && sudo make install && sudo ldconfig 

# Install srsRAN 4G
RUN wget https://github.com/srsran/srsRAN_4G/archive/refs/heads/master.zip
RUN unzip master.zip && \
        mv srsRAN_4G-master srsRAN

RUN apt-get update -y && \
	apt-get install -y cmake \
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

COPY onboot.sh /srsRAN/build/
COPY multiUE.py /srsRAN/build/

RUN apt install iperf3 -y

RUN chmod +x /srsRAN/build/onboot.sh
CMD ["./srsRAN/build/onboot.sh"] 

# For conecting via Open SSL
EXPOSE 22

