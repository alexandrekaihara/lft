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


To build the seafile server image it is necessary to create a adapter on host with the IP which will be configured on the seafile server.

This IP is fixed in order to simplify the execution and setting up the experiment. 

If you wish to change the seafile IP, you must change it on the the first line of setup.sh file and change the ip address of the network adapter of build.sh file.

The following commands must be used to build this image.

sudo chmod +x build.sh
./build.sh
