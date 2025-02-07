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

SUBDIRS = gnome
dist_bin_SCRIPTS  = liveinst

desktopdir         = $(datadir)/applications
dist_desktop_DATA  = liveinst.desktop

dist_libexec_SCRIPTS = liveinst-setup.sh \
                       locale1-x11-sync

systemddir = $(prefix)/lib/systemd/user
dist_systemd_DATA = locale1-x11-sync.service

autostartdir       = $(sysconfdir)/xdg/autostart
dist_autostart_DATA = liveinst-setup.desktop

polkitdir           = $(datadir)/polkit-1/actions
dist_polkit_DATA    = org.fedoraproject.pkexec.liveinst.policy

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

EXTRA_DIST = README

MAINTAINERCLEANFILES = Makefile.in
