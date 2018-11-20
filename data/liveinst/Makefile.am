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

SUBDIRS = console.apps gnome pam.d

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
# Use the merged translations in $(builddir). If no merged translations exist,
# just exit.
install-data-hook:
	for p in $(top_builddir)/po/*.mpo ; do \
	    [ -e $$p ] || exit 0 ; \
	    $(MSGFMT) --desktop --template=$(DESTDIR)$(desktopdir)/liveinst.desktop \
	        --locale=$$(basename $$p .mpo) \
		-o $(DESTDIR)$(desktopdir)/liveinst.desktop.new $$p || exit 1 ; \
	    mv $(DESTDIR)$(desktopdir)/liveinst.desktop.new $(DESTDIR)$(desktopdir)/liveinst.desktop || exit 1 ; \
	done

uninstall-local:
	rm -f $(DESTDIR)$(bindir)/liveinst

EXTRA_DIST = README

MAINTAINERCLEANFILES = Makefile.in
