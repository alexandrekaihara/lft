#!/bin/bash 

apt-get update -y
apt-get upgrade -y

#declare -a versionsAptGet=("=1:8.2p1-4ubuntu0.3" "=2.0.6"    ""     "=1.3-20190808-1" "=3.0pl1-136ubuntu1" "=0.99.9.8"                  "=0.8.12-1ubuntu4" ""     ""      "=2.2.19-3ubuntu2.1" "" "" "" "" "")
declare -a packagesAptGet=("docker.io" "python3" "iproute2" "iptables" "openvswitch-switch" "python3-pip" "firewalld" "nfdump")
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

pip install pandas
