# systemd/Makefile.am for anaconda
#
# Copyright (C) 2011  Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published
# by the Free Software Foundation; either version 2.1 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Author: Chris Lumens <clumens@redhat.com>

systemddir           = /lib/systemd/system
dist_systemd_DATA = anaconda-shell.service anaconda.target loader.service tmp.mount

MAINTAINERCLEANFILES = Makefile.in

install-exec-local:
	mkdir -p $(DESTDIR)/lib/systemd/system/anaconda.target.wants
	ln -sf /lib/systemd/system/anaconda-shell.service $(DESTDIR)/lib/systemd/system/anaconda.target.wants
	ln -sf /lib/systemd/system/dbus.target $(DESTDIR)/lib/systemd/system/anaconda.target.wants
	ln -sf /lib/systemd/system/loader.service $(DESTDIR)/lib/systemd/system/anaconda.target.wants
	ln -sf /lib/systemd/system/sockets.target $(DESTDIR)/lib/systemd/system/anaconda.target.wants
	ln -sf /lib/systemd/system/udev.service $(DESTDIR)/lib/systemd/system/anaconda.target.wants
	ln -sf /lib/systemd/system/udev-settle.service $(DESTDIR)/lib/systemd/system/anaconda.target.wants
