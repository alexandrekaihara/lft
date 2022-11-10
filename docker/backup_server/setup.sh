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


# Set system time 
ln -s /usr/share/zoneinfo/Europe/Berlin /etc/localtime

# Update the system
apt-get -y update
apt-get -y upgrade

# Create samba configuration 
## Create directory for samba 
mkdir /media/backup
chmod 777 /media/backup
# create mask und force create mode (necessary for overwriting files in the Inbox)
cat > /etc/samba/smb.conf <<EOF
[global]
workgroup = WORKGROUP
security = user
map to guest = bad user

[backup]
comment = Backup for all servers 
path = /media/backup
read only = no
guest ok = yes
create mask = 777
force create mode = 777
EOF

# Delete the folders regularly to save memory 
echo -e "" > /var/log/cron.log
echo -e "0 20 * * * rm -r /media/backup/* >> /var/log/cron.log 2>&1" >> mycron
## Create Cron-Daemon which deletes every night at 01:00 the backup folders 
echo -e "0 1 * * * apt-get update -y && apt-get upgrade -y >> /var/log/cron.log 2>&1" >> mycron
crontab mycron
rm mycron

# Create user login for SSH (create user with appropriate password)
useradd -m -s /bin/bash mininet
echo "mininet:mininet" | chpasswd
usermod -a -G sudo mininet

# Prettify Prompt 
mkdir /home/debian
echo -e "PS1='\[\033[1;37m\]\[\e]0;\u@\h: \w\a\]${debian_chroot:+($debian_chroot)}\u@\h:\[\033[41;37m\]\w\$\[\033[0m\] '" >> /home/debian/.bashrc

