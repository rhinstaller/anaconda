# liveinst/Makefile.am for anaconda
#
# Copyright (C) 2009  Red Hat, Inc.
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
# Author: David Cantrell <dcantrell@redhat.com>

SUBDIRS = console.apps gnome pam.d

if IS_LIVEINST_ARCH
dist_sbin_SCRIPTS  = liveinst

desktopdir         = $(datadir)/applications
desktop_DATA       = liveinst.desktop

xinitdir           = /etc/X11/xinit/xinitrc.d
dist_xinit_SCRIPTS = zz-liveinst.sh
endif

EXTRA_DIST = README liveinst.desktop.in

CLEANFILES = liveinst.desktop *.h

MAINTAINERCLEANFILES = Makefile.in

@INTLTOOL_DESKTOP_RULE@

install-exec-local:
	mkdir -p $(DESTDIR)$(bindir)
	ln -s consolehelper $(DESTDIR)$(bindir)/liveinst

uninstall-local:
	rm -f $(DESTDIR)$(bindir)/liveinst
	for d in $(DESTDIR)$(bindir) ; do
		while [ ! -z "$$d" ]; do \
			rmdir $$d 2>/dev/null ; \
			d="`dirname $$d`" ; \
		done ; \
	done
