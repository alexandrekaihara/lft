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


DBHOST=localhost
DBUSERNAME=root
DBUSERPASS=PWfMS2015
DBNAME=postfixdb

if [ -n "$2" ]; then
    echo "input ok"
else
	echo "Correct usage: sh script.sh username domain"
    exit
fi

username=$1@$2
password=\$1\$f258886e\$mthkVuLZBDNEfnDbH3Gg51
maildir=$2/$1/
quota=0
local_part=$1
domain=$2


mysql --host=$DHBOST --user=$DBUSERNAME --password=$DBUSERPASS postfixdb << EOF
insert into mailbox (username,password, name, maildir,quota,local_part,domain) values('$username','$password', ' ', '$maildir','$quota','$local_part','$domain');
EOF

address=$1@$2
goto=$1@$2
domain=$2
active=1

mysql --host=$DHBOST --user=$DBUSERNAME --password=$DBUSERPASS postfixdb << EOF
insert into alias (address,goto,domain,active) values('$address','$goto','$domain','$active');
EOF
