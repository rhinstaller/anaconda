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
dist_desktop_DATA  = liveinst.desktop

dist_libexec_SCRIPTS = liveinst-setup.sh

autostartdir       = $(sysconfdir)/xdg/autostart
dist_autostart_DATA = liveinst-setup.desktop

install-exec-local:
	$(MKDIR_P) $(DESTDIR)$(bindir)
	$(LN_S) consolehelper $(DESTDIR)$(bindir)/liveinst

# Merge translations into the desktop file
install-data-hook:
	$(MSGFMT) --desktop --template $(srcdir)/liveinst.desktop -d $(top_srcdir)/po \
		-o $(DESTDIR)$(desktopdir)/liveinst.desktop

uninstall-local:
	rm -f $(DESTDIR)$(bindir)/liveinst
endif

EXTRA_DIST = README

MAINTAINERCLEANFILES = Makefile.in
