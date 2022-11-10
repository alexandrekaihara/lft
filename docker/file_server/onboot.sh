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


# Create dummy files 
dd if=/dev/zero of=/media/storage/file30kB.dat bs=1K count=30
dd if=/dev/zero of=/media/storage/file40kB.dat bs=1K count=40
dd if=/dev/zero of=/media/storage/file50kB.dat bs=1K count=50
dd if=/dev/zero of=/media/storage/file100kB.dat bs=1K count=100
dd if=/dev/zero of=/media/storage/file500kB.dat bs=1K count=500
dd if=/dev/zero of=/media/storage/file1MB.dat bs=1M count=1
dd if=/dev/zero of=/media/storage/file2MB.dat bs=1M count=2
dd if=/dev/zero of=/media/storage/file3MB.dat bs=1M count=3
dd if=/dev/zero of=/media/storage/file4MB.dat bs=1M count=4
dd if=/dev/zero of=/media/storage/file5MB.dat bs=1M count=5
dd if=/dev/zero of=/media/storage/file6MB.dat bs=1M count=6
dd if=/dev/zero of=/media/storage/file7MB.dat bs=1M count=7
dd if=/dev/zero of=/media/storage/file8MB.dat bs=1M count=8
dd if=/dev/zero of=/media/storage/file9MB.dat bs=1M count=9
dd if=/dev/zero of=/media/storage/file10MB.dat bs=1M count=10
dd if=/dev/zero of=/media/storage/file50MB.dat bs=1M count=50
dd if=/dev/zero of=/media/storage/file100MB.dat bs=1M count=100
dd if=/dev/zero of=/media/storage/file300MB.dat bs=1M count=300
dd if=/dev/zero of=/media/storage/file700MB.dat bs=1M count=700

# Start services
service smbd start
service ssh start
service cron start

# Keep alive
tail -f /dev/null