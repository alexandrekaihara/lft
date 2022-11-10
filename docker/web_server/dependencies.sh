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


# Update
until apt-get -y --error-on=any update 2> /tmp/apt-get-update-error
do
  echo "Error on apt-get update"
done
apt upgrade -y

# Download basic packages 
#declare -a versionsAptGet=("=1:8.2p1-4ubuntu0.3" "=2.0.6" "" "=1.3-20190808-1" "=3.0pl1-136ubuntu1" "=0.99.9.8" "=0.8.12-1ubuntu4" "" "" "" "" "" "")
declare -a packagesAptGet=("ssh" "apt-utils" "sudo" "dialog"  "cron" "software-properties-common" "aptitude" "nano" "iptables" "net-tools" "iproute2" "iputils-ping" "traceroute")
count=${#packagesAptGet[@]}
for i in `seq 1 $count` 
do
  until dpkg -s ${packagesAptGet[$i-1]} | grep -q Status;
  do
    #RUNLEVEL=1 apt install -y --no-install-recommends ${packagesAptGet[$i-1]}${versionsAptGet[$i-1]}
    RUNLEVEL=1 apt install -y --no-install-recommends ${packagesAptGet[$i-1]}
  done
  echo "${packagesAptGet[$i-1]} found."
done

# Solve basic problems on missing packages and configurations on Ubuntu's Docker image :
## 1.1 Policy-rc.d not permit start process on reboot
printf '#!/bin/sh\nexit 0' > /usr/sbin/policy-rc.d
## 1.2 Failed to create symbolic link em /etc/resolv.conf https://stackoverflow.com/questions/40877643/apt-get-install-in-ubuntu-16-04-docker-image-etc-resolv-conf-device-or-reso
echo 'debconf debconf/frontend select Noninteractive' | debconf-set-selections
echo "resolvconf resolvconf/linkify-resolvconf boolean false" | debconf-set-selections
until dpkg -s resolvconf | grep -q Status;
do
  RUNLEVEL=1 apt install -y --no-install-recommends resolvconf=1.82
done
apt-get update

# Install all predefined packages 
#declare -a versionsAptGet=("2.4.41-4ubuntu3.8" "6.0-25ubuntu1" "3.1.3-8")
declare -a packagesAptGet=("apache2" "unzip" "rsync" "cron")
count=${#packagesAptGet[@]}
for i in `seq 1 $count` 
do
until dpkg -s ${packagesAptGet[$i-1]} | grep -q Status;
do
RUNLEVEL=1 apt install -y --no-install-recommends ${packagesAptGet[$i-1]}
done
done

# System update
apt-get -y update
apt-get -y upgrade
