# liveinst/gnome/Makefile.am for anaconda
#
# Copyright (C) 2012  Red Hat, Inc.
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

welcomedir              = $(datadir)/$(PACKAGE_NAME)/gnome
dist_welcome_DATA       = rhel-welcome.desktop
dist_welcome_SCRIPTS    = rhel-welcome.js

MAINTAINERCLEANFILES = Makefile.in

# Merge the translations into the desktop file
# Use the merged translations in $(builddir). If no merged translations exist,
# just exit.
# Rename rhel-welcome.js to just rhel-welcome
install-data-hook:
	for p in $(top_builddir)/po/*.mpo ; do \
	    [ -e $$p ] || exit 0 ; \
	    $(MSGFMT) --desktop --template=$(DESTDIR)$(welcomedir)/rhel-welcome.desktop \
	        --locale=$$(basename $$p .mpo) \
		-o $(DESTDIR)$(welcomedir)/rhel-welcome.desktop.new $$p || exit 1 ; \
	    mv $(DESTDIR)$(welcomedir)/rhel-welcome.desktop.new $(DESTDIR)$(welcomedir)/rhel-welcome.desktop || exit 1 ; \
	done
	cd $(DESTDIR)$(welcomedir) && mv rhel-welcome.js rhel-welcome

uninstall-hook:
	-cd $(DESTDIR)$(welcomedir) && rm -f rhel-welcome
