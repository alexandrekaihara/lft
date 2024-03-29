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

# docker run -d --privileged alexandremitsurukaihara/lft:perfonar-toolkit
# docker exec -it {containerid} /bin/bash

/usr/lib/perfsonar/scripts/service_watcher

systemctl start pscheduler-scheduler
systemctl start pscheduler-runner
systemctl start pscheduler-archiver
systemctl start pscheduler-ticker
systemctl start psconfig-pscheduler-agent
systemctl start perfsonar-lsregistrationdaemon
systemctl start owamp-server

# Keep alive
tail -f /dev/null
