#!/bin/bash

apt install -y software-properties-common gpg-agent
cd /etc/apt/sources.list.d/
curl -o perfsonar-release.list http://downloads.perfsonar.net/debian/perfsonar-release.list
curl http://downloads.perfsonar.net/debian/perfsonar-official.gpg.key | tac | tac | apt-key add -
apt update
apt install -y perfsonar-toolkit


# Install Mininet-Wifi
git clone git://github.com/intrig-unicamp/mininet-wifi
cd mininet-wifi
sudo util/install.sh -Wlnfv

# Install Container Net
sudo apt-get install -y ansible git aptitude 
pip install docker
git clone https://github.com/ramonfontes/containernet.git
sudo util/install.sh -W
mv containernet/containernet ../