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
rm /etc/localtime
ln -s /usr/share/zoneinfo/Europe/Berlin /etc/localtime

# Mount the mount point to the backupserver
mkdir /home/debian
mkdir /home/debian/backup

# Delete the folders regularly to save memory 
echo -e "" > /var/log/cron.log
# Run the script to set up the backup server on a regular basis
echo -e "55 21 * * * python3 /home/debian/backup.py >> /var/log/cron.log 2>&1" >> mycron
# Run backup service periodically
echo -e "0 22 * * * tar -czf /home/debian/backup/backup_webserver.tar.gz /var/www/  >> /var/log/cron.log 2>&1" >> mycron
# Update frequently
echo -e "0 1 * * * apt-get update -y && apt-get upgrade -y >> /var/log/cron.log 2>&1" >> mycron
crontab mycron
rm mycron

# User for ssh logins
useradd -m -s /bin/bash mininet
echo "mininet:mininet" | chpasswd
usermod -a -G sudo mininet

# Prettify Prompt 
echo -e "PS1='\[\033[1;37m\]\[\e]0;\u@\h: \w\a\]${debian_chroot:+($debian_chroot)}\u@\h:\[\033[41;37m\]\w\$\[\033[0m\] '" >> /home/debian/.bashrc