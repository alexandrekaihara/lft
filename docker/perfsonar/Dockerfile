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


FROM centos:centos7

RUN yum -y update && \
        yum -y install epel-release openssh-server && \
        yum -y install http://software.internet2.edu/rpms/el7/x86_64/latest/packages/perfsonar-repo-0.11-1.noarch.rpm && \
        yum clean all

RUN  yum -y install perfsonar-toolkit

COPY onboot.sh /

RUN chmod +x /onboot.sh

CMD ["./onboot.sh"] 

# For conecting via Open SSL
EXPOSE 22
EXPOSE 80

