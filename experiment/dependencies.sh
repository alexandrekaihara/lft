#!/bin/bash

apt install -y software-properties-common gpg-agent
cd /etc/apt/sources.list.d/
curl -o perfsonar-release.list http://downloads.perfsonar.net/debian/perfsonar-release.list
curl http://downloads.perfsonar.net/debian/perfsonar-official.gpg.key | tac | tac | apt-key add -
apt update
apt install -y perfsonar-toolkit
