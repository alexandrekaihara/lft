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


# Imports
FROM ubuntu:20.04

# Updates
COPY dependencies.sh .
RUN chmod +x dependencies.sh \
&& ./dependencies.sh \
&& sudo su

# Copy the backup file, genDomain e genUser
RUN mkdir /home/debian \
&& mkdir /tmp/mailsetup
COPY mailscripts/genUser.sh        /tmp/mailsetup
COPY mailscripts/genDomain.sh      /tmp/mailsetup
COPY mailscripts/mysql_conf.sh     /tmp/mailsetup
COPY mailscripts/config_inc_php.sh /tmp/mailsetup
COPY mailscripts/postfix_config.sh /tmp/mailsetup
COPY mailscripts/dovecot_config.sh /tmp/mailsetup

# Start setup
COPY setup.sh .
RUN chmod +x setup.sh\
&& ./setup.sh

# Start samba and dummy files on start
COPY onboot.sh /home
RUN chmod +x /home/onboot.sh
CMD ["./home/onboot.sh"]

# For conecting via Open SSL
EXPOSE 22
EXPOSE 587

