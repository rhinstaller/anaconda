#
# Makefile
#
# Copyright (C) 2007  Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

all: liveinst.desktop

liveinst.desktop: liveinst.desktop.in
	LC_ALL=C intltool-merge -d -u ../po liveinst.desktop.in liveinst.desktop

install:
	mkdir -p $(DESTDIR)/usr/bin
	mkdir -p $(DESTDIR)/usr/sbin
	mkdir -p $(DESTDIR)/usr/share/applications
	mkdir -p $(DESTDIR)/etc/pam.d $(DESTDIR)/etc/security/console.apps
	mkdir -p $(DESTDIR)/etc/X11/xinit/xinitrc.d

	install -m 0755 liveinst.sh $(DESTDIR)/usr/sbin/liveinst
	ln -s consolehelper $(DESTDIR)/usr/bin/liveinst

	install -m 0644 liveinst.pam $(DESTDIR)/etc/pam.d/liveinst
	install -m 0644 liveinst.console $(DESTDIR)/etc/security/console.apps/liveinst

	install -m 0644 liveinst.desktop $(DESTDIR)/usr/share/applications

	install -m 0755 liveinst.xinit $(DESTDIR)/etc/X11/xinit/xinitrc.d/zz-liveinst.sh

clean:
	rm -f *~ liveinst.desktop

depend:

