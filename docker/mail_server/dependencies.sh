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
#declare -a versionsAptGet=("=1:8.2p1-4ubuntu0.3" "=2.0.6" "" "=1.3-20190808-1" "=3.0pl1-136ubuntu1" "=0.99.9.8" "=0.8.12-1ubuntu4" "" "" "" "" "")
declare -a packagesAptGet=("ssh"   "apt-utils" "sudo" "dialog"  "cron" "software-properties-common" "aptitude" "nano" "iptables" "net-tools" "iproute2" "iputils-ping")
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

# Solve problems on installing cups:
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

# Correction for installing the php5.6
dpkg -l | grep php| awk '{print $2}' |tr "\n" " "
sudo aptitude purge `dpkg -l | grep php| awk '{print $2}' |tr "\n" " "`
until dpkg -s php5.6 | grep -q Status;
do
  echo "\n" | sudo add-apt-repository ppa:ondrej/php
  RUNLEVEL=1 apt install -y --no-install-recommends php5.6=5.6.40-57+ubuntu20.04.1+deb.sury.org+1
done
sudo apt-get update

# Resolve MySQLd missing directory: https://stackoverflow.com/questions/34954455/mysql-daemon-lock-issue
mkdir /var/run/mysqld
chmod 777 /var/run/mysqld

# Define the packets to install with apt-get 
#declare -a versionsAptGet=("=8.0.27-0ubuntu0.20.04.1" "" "" "" "=2.4.41-4ubuntu3.8" "=1:2.3.7.2-1ubuntu3.5" "=1:2.3.7.2-1ubuntu3.5" "=1:2.3.7.2-1ubuntu3.5" "=1:2.3.7.2-1ubuntu3.5" "=3.4.13-0ubuntu1.2" "=3.4.13-0ubuntu1.2" "=7.68.0-1ubuntu2.7" "=5.5.6" "=7.4.0-2" "=1.20.3-1ubuntu1")
declare -a packagesAptGet=("mysql-server" "php5.6-mysql" "php5.6-imap" "php5.6-mbstring" "apache2" "dovecot-core" "dovecot-mysql" "dovecot-imapd" "dovecot-pop3d" "postfix" "postfix-mysql" "curl" "whois" "dos2unix" "wget" "samba")
count=${#packagesAptGet[@]}
for i in `seq 1 $count` 
do
    until dpkg -s ${packagesAptGet[$i-1]} | grep -q Status;
  do
    #RUNLEVEL=1 apt-get --force-yes --yes --no-install-recommends install ${packagesAptGet[$i-1]}${versionsAptGet[$i-1]}
    RUNLEVEL=1 apt-get --force-yes --yes --no-install-recommends install ${packagesAptGet[$i-1]}
  done
done

# Continuation of MySQLd solution
chown mysql:mysql /var/run/mysqld
