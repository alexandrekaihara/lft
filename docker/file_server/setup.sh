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


#https://manual.seafile.com/deploy/using_mysql/

# Set system time 
rm /etc/localtime
ln -s /usr/share/zoneinfo/Europe/Berlin /etc/localtime

# Update the system
apt-get -y update
apt-get -y upgrade

# Directory in which files can be copied
# The Inbox is necessary to avoid race conditions when writing to Netstorage
mkdir /media/storage
mkdir /media/storage/inbox
chmod 777 /media/storage/inbox

# Create Samba configuration 
# create mask und force create mode (necessary for overwriting files in the Inbox)
cat > /etc/samba/smb.conf <<EOF
[global]
workgroup = WORKGROUP
security = user
map to guest = bad user
[netstorage]
comment = Netstorage fuer Openmininet-VMs
path = /media/storage
read only = no
guest ok = yes
create mask = 777
force create mode = 777
EOF

# Mount the mount point for backup
mkdir /home/debian
mkdir /home/debian/backup/
chmod 777 /home/debian/backup

# Create log for cron
echo -e "" > /var/log/cron.log
# Run the script to set up the backup server on a regular time interval 
echo -e "55 21 * * * python3 /home/debian/backup.py >> /var/log/cron.log 2>&1" >> mycron
# Run backup service periodically
echo -e "0 22 * * * tar -cf /home/debian/backup/backup.tar /media/storage/ >> /var/log/cron.log 2>&1" >> mycron
# Cron daemon set up every night at 12:00 clock to delete all files from the inbox 
echo -e "0 0 * * * rm -r /media/storage/inbox/* >> /var/log/cron.log 2>&1" >> mycron
# Cron daemon set up to make every night at 01:00 clock updates
echo -e "0 1 * * * apt-get update -y && apt-get upgrade -y >> /var/log/cron.log 2>&1" >> mycron
crontab mycron
rm mycron

# Prepare for ssh user login (create mininet user with appropriate password)
useradd -m -s /bin/bash mininet
echo "mininet:mininet" | chpasswd
usermod -a -G sudo mininet

# Prettify Prompt
echo -e "PS1='\[\033[1;37m\]\[\e]0;\u@\h: \w\a\]${debian_chroot:+($debian_chroot)}\u@\h:\[\033[41;37m\]\w\$\[\033[0m\] '" >> /home/debian/.bashrc


