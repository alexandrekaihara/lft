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


# IP address on which seafile server will be listening to (change here)
IP='192.168.50.1'

# Create seafile user 
echo -e 'rootpassword\nrootpassword' | passwd root
useradd -m -s /bin/bash seafile
echo -e '123\n123' | passwd seafile
# ERROR Username is not in the sudoers file https://unix.stackexchange.com/questions/179954/username-is-not-in-the-sudoers-file-this-incident-will-be-reported 
adduser seafile sudo
chmod  0440  /etc/sudoers
#reboot

# Se der problema de protocol not supported https://techglimpse.com/nginx-error-address-family-solution/
sed -i "s/listen \[\:\:\]\:80 default_server;/#listen \[\:\:\]\:80 default_server;/g" /etc/nginx/sites-enabled/default
service nginx start

# DB Setup (mariadb)
service mysql start
echo -e 'rootpassword\nn\nY\nY\nY\nY\n' | mysql_secure_installation
mysql -u root --password=123 -e 'create database `ccnet-db` character set = 'utf8';'
mysql -u root --password=123 -e 'create database `seafile-db` character set = 'utf8';'
mysql -u root --password=123 -e 'create database `seahub-db` character set = 'utf8';'
mysql -u root --password=123 -e 'create user 'seafile'@'localhost';'
mysql -u root --password=123 -e 'set password for 'seafile'@'localhost' = password("Password123");'
mysql -u root --password=123 -e 'GRANT ALL PRIVILEGES ON `ccnet-db`.* to `seafile`@localhost;'
mysql -u root --password=123 -e 'GRANT ALL PRIVILEGES ON `seafile-db`.* to `seafile`@localhost;'
mysql -u root --password=123 -e 'GRANT ALL PRIVILEGES ON `seahub-db`.* to `seafile`@localhost;'
mysql -u root --password=123 -e 'FLUSH PRIVILEGES;'

# Seafile Setup 
wget O /var/eafile-server_7.1.5_x86-64.tar.gz https://s3.eu-central-1.amazonaws.com/download.seadrive.org/seafile-server_7.1.5_x86-64.tar.gz
tar xzvf seafile-server_7.1.5_x86-64.tar.gz -C /opt
rm -rf /opt/seafile-server_7.1.5_x86-64.tar.gz
chown -R seafile:seafile /opt/seafile-server-7.1.5

# Change server name to the right ip address
cat > /etc/nginx/conf.d/seafile.conf << \EOF
server {
    #listen [::]:80;
    listen 80;
    server_name  replacehere;
    autoindex off;
    client_max_body_size 100M;
    access_log /var/log/nginx/seafile.com.access.log;
    error_log /var/log/nginx/seafile.com.error.log;

     location / {
            proxy_pass         http://127.0.0.1:8000;
            proxy_set_header   Host $host;
            proxy_set_header   X-Real-IP $remote_addr;
            proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header   X-Forwarded-Host $server_name;
            proxy_read_timeout  1200s;
        }

     location /seafhttp {
            rewrite ^/seafhttp(.*)$ $1 break;
            proxy_pass http://127.0.0.1:8082;
            proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_connect_timeout  36000s;
            proxy_read_timeout  36000s;
            proxy_send_timeout  36000s;
            send_timeout  36000s;
        }

    location /media {
            root /opt/seafile-server-latest/seahub;
        }
}
EOF

# Start programs
service ssh start
service mysql start
service nginx start

# Waiting for network configuration
# Finish seafile configuration
cd /opt/seafile-server-7.1.5/
## Correction on python script to avoid stopping container execution when asking for password
sed -i 's/password = Utils.ask_question(question, key=key, password=True)/password = \"Password123\"/1' setup-seafile-mysql.py
## Config Seafile
echo 'Found host IP '"$IP"
chmod +x setup-seafile-mysql.sh
echo -e '\nseafileserver\n'"$IP"'\n8082\n2\nlocalhost\n3306\nseafile\nccnet-db\nseafile-db\nseahub-db\n' | ./setup-seafile-mysql.sh
mkdir /opt/logs
mkdir /opt/pids
## Config nginx
sed -i 's/replacehere/'"$IP"'/g' /etc/nginx/conf.d/seafile.conf
service nginx restart

# Seafile start
cd /opt/seafile-server-latest
./seafile.sh start
## Correction on python script to avoid stopping container execution when asking for password
sed -i "s/key = 'admin password'/return 'Password123'/1" check_init_admin.py
echo -e 'alexandreamk1@gmail.com' | ./seahub.sh start

# Must login on seafile server in order to create a user folder to enable synchronizing with clients
export PATH="$PATH:/opt/"
until [ ! -z $SEAFOLDER ]; do
python3 /home/login_seafile_page.py
mysql -uroot --password=Password123 -e "USE seafile-db; SELECT * FROM RepoOwner" | grep alexandreamk1@gmail.com > /home/seafolder
sed -i "s/2\t//1" /home/seafolder
sed -i "s/\talexandreamk1@gmail.com//1" /home/seafolder
SEAFOLDER=$(cat /home/seafolder)
if [ ! -z $SEAFOLDER ]; then 
echo "Seafolder successfully created with ID "$SEAFOLDER; else
echo "Login failed, restarting process..."; fi
done