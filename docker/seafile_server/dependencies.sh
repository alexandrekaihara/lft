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
## These libraries are necessary for Chrome driver for Selenium scripts (libglib2.0-0 libnss3 libgconf-2-4 libfontconfig1)
declare -a packagesAptGet=("systemctl" "apt-utils" "sudo" "dialog" "cron" "software-properties-common" "aptitude" "ssh" "nano" "iptables" "net-tools" "iproute2" "iputils-ping" "python3" "python3-pip" "libpython3.8" "python3-setuptools" "python3-pil" "python3-ldap" "python3-urllib3" "ffmpeg" "python3-pip" "python3-mysqldb" "python3-memcache" "python3-requests" "libmemcached-dev" "mariadb-server" "nginx" "wget" "python3-dev" "build-essential" "libpq-dev" "gcc" "unzip" "firefox") #"libssl-dev" "libffi-dev" "libxml2-dev" "libxslt1-dev" "zlib1g-dev")
count=${#packagesAptGet[@]}
for i in `seq 1 $count` 
do
  until dpkg -s ${packagesAptGet[$i-1]} | grep -q Status;
  do
    RUNLEVEL=1 apt install -y --no-install-recommends ${packagesAptGet[$i-1]}
  done
  echo "${packagesAptGet[$i-1]} found."
done


# Install python dependencies
python3 -m pip install --upgrade pip
pip3 install --timeout=3600 Pillow pylibmc captcha jinja2 sqlalchemy psd-tools django-pylibmc django-simple-captcha python3-ldap selenium


# Install Geckodriver for Selenium
until mv geckodriver /opt/
do
  wget "https://github.com/mozilla/geckodriver/releases/download/v0.30.0/geckodriver-v0.30.0-linux64.tar.gz"
  tar -xzf "geckodriver-v0.30.0-linux64.tar.gz"
done
rm geckodriver-v0.30.0-linux64.tar.gz
