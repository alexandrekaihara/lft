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

if [ -n "$1" ]; then
    echo "input ok"
else
    echo "Correct usage: sh script.sh domain"
    exit
fi

domain=$1
aliases=10
mailboxes=10
maxquota=10
quota=2048
transport=virtual
backupmx=0
active=1

mysql --host=$DHBOST --user=$DBUSERNAME --password=$DBUSERPASS postfixdb << EOF
insert into domain (domain, description,aliases,mailboxes,maxquota,quota,transport,backupmx,active) values('$domain', ' ', '$aliases','$mailboxes','$maxquota','$quota','$transport','$backupmx','$active');
EOF