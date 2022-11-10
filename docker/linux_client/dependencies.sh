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
apt-get update -y
apt-get upgrade -y

#declare -a versionsAptGet=("=1:8.2p1-4ubuntu0.3" "=2.0.6"    ""     "=1.3-20190808-1" "=3.0pl1-136ubuntu1" "=0.99.9.8"                  "=0.8.12-1ubuntu4" ""     ""      "=2.2.19-3ubuntu2.1" "" "" "" "" "")
declare -a packagesAptGet=("openssh-client"     "apt-utils" "sudo" "dialog"          "cron"               "software-properties-common" "aptitude"         "wget" "unzip" "dirmngr" "nano" "iptables" "net-tools" "iproute2" "iputils-ping")
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
apt-get update -y

# From Ubuntu 18 and later, there is no support for libqt4-dev, so must run the following commands
until dpkg -s libqt4-dev | grep -q Status;
do
    echo "\n" | sudo add-apt-repository ppa:rock-core/qt4
    apt-get install -y --no-install-recommends libqt4-dev=5:4.8.7+dfsg-7ubuntu4rock7
done

# Add sources  
sudo aptitude update
sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys 8756C4F765C9AC3CB6B85D62379CE192D401AB61
echo deb http://dl.bintray.com/seafile-org/deb strech main | sudo tee /etc/apt/sources.list.d/seafile.list

# Update the system 
apt-get -y update
apt-get -y upgrade

# Install Geckodriver for Selenium
until mv geckodriver /opt/
do
  wget "https://github.com/mozilla/geckodriver/releases/download/v0.30.0/geckodriver-v0.30.0-linux64.tar.gz"
  tar -xzf "geckodriver-v0.30.0-linux64.tar.gz"
done
rm geckodriver-v0.30.0-linux64.tar.gz
export PATH="$PATH:/opt/"

# Install all predefined packages
declare -a packagesAptGet=("aptitude"         "python3"         "python3-xlib"  "python3-pip"        "firefox"                         "xvfb"                        "unzip"         "cups"              "cups-client"       "cups-bsd"          "cifs-utils"        "cmake"            "sqlite3"            "python3-setuptools" "python3-simplejson" "autoconf"   "automake"          "libtool"    "libevent-dev"     "libcurl4-openssl-dev" "libgtk2.0-dev"     "uuid-dev"           "intltool"         "libsqlite3-dev"     "valac"            "libjansson-dev" "libfuse2" "seafile-cli" "grub2"              "nmap"                "python3.8-dev"            "libcups2-dev"      "gcc"               "firefox-geckodriver"           ) 
count=${#packagesAptGet[@]}
for i in `seq 1 $count`
do
until dpkg -s ${packagesAptGet[$i-1]} | grep -q Status;
do
apt-get install -y --no-install-recommends --force-yes ${packagesAptGet[$i-1]}${versionsAptGet[$i-1]}
done
echo "${packagesAptGet[$i-1]} found."
done

# Definition of the Python-Libraries to install 
python3 -m pip install --upgrade pip
#declare -a versionsPip=("==3.141.0" "==8.4.0" "==2.2" "==0.2.9" "==4.8.0" "==0.7.1" "==2.0.1")
declare -a packagesPip=("selenium" "pillow" "pyvirtualdisplay" "xvfbwrapper" "pexpect" "python-nmap" "pycups")
count=${#packagesPip[@]}
for i in `seq 1 $count`
    do
    echo "Looking for package ${packagesPip[$i-1]}."
    until pip3 show ${packagesPip[$i-1]} | grep -q Location;
    do
        echo "${packagesPip[$i-1]} not found. Installing..."
        #pip3 install ${packagesPip[$i-1]}${versionsPip[$i-1]}
        pip3 install ${packagesPip[$i-1]}
    done
    echo "${packagesPip[$i-1]} found."
done

# Update the system 
aptitude -y update
aptitude -y upgrade
