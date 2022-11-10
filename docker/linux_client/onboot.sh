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


# Waiting for network configuration
IP=$(hostname -I)
until [ ! -z $IP ]; do
IP=$(hostname -I)
echo "Waiting for network configuration"
sleep 1
done 
$ONBOOTLOG="${IP}_onboot.log"

# Open Brackets to send all outputs into a log file
{

# Move all configure files received
#mv /home/debian/printerip        /home/debian/automation/packages/system/printerip   
#mv /home/debian/config.ini       /home/debian/automation/packages/system/config.ini
#mv /home/debian/serverconfig.ini /home/debian/automation/packages/system/serverconfig.ini
#mv /home/debian/sshiplist.ini    /home/debian/automation/packages/system/sshiplist.ini > /dev/null 2>&1
#mv /home/debian/ipList.txt       /home/debian/automation/packages/attacking/ipList.txt > /dev/null 2>&1
#mv /home/debian/ipListPort80.txt /home/debian/automation/packages/attacking/ipListPort80.txt > /dev/null 2>&1
#mv /home/debian/iprange.txt      /home/debian/automation/packages/attacking/iprange.txt > /dev/null 2>&1

# Configure printer 
/etc/init.d/cups start
printerip=`cat /home/debian/automation/packages/system/printerip` 
if [ ! "$printerip" = "0.0.0.0" ]; then 
  lpadmin -p PDF -v socket://$printerip -E
  /etc/init.d/cups restart
fi

# Configure Seafile
mkdir -pv /home/debian/sea /home/debian/seafile-client
until test -e /home/debian/.ccnet
do
seaf-cli init -d /home/debian/seafile-client -c /home/debian/.ccnet
done
until seaf-cli config -k disable_verify_certificate -v true -c /home/debian/.ccnet
do
seaf-cli start -c /home/debian/.ccnet
done
seaf-cli config -k enable_http_sync -v true -c /home/debian/.ccnet 
seaf-cli stop -c /home/debian/.ccnet
seaf-cli start -c /home/debian/.ccnet
chown -R mininet:mininet /home/debian/sea/ /home/debian/seafile-client/ /home/debian/.ccnet

} > "/home/debian/log/${IP}_onboot.log"

# add PATH to geckodriver for browsing.py to use Selenium
export PATH="$PATH:/opt/"

# Keep alive
until cd /home/debian/automation
do 
  sleep 1
done

until false
do
  python3 readIni.py >> "/home/debian/log/${IP}_onboot.log"
done
