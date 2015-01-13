# data/window-manager/config/Makefile.am for anaconda
#
# Copyright (C) 2015  Red Hat, Inc.
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
# Author: David Shea <dshea@redhat.com>

schemadir = $(pkgdatadir)/window-manager/glib-2.0/schemas

# These files need to be compiled by glib-compile-schemas. This is handled
# in the spec file scriptlets.
dist_schema_DATA = org.gnome.desktop.wm.keybindings.gschema.override \
		   org.gnome.desktop.wm.preferences.gschema.override

# GSettings insists on the override files being in the same directory as the
# schemas they modify, so pretend that this is the case with symlinks and
# create the compiled schema.
install-data-hook:
	$(MKDIR_P) $(DESTDIR)$(schemadir)
	$(LN_S) -f /usr/share/glib-2.0/schemas/org.gnome.desktop.wm.keybindings.gschema.xml $(DESTDIR)$(schemadir)
	$(LN_S) -f /usr/share/glib-2.0/schemas/org.gnome.desktop.wm.preferences.gschema.xml $(DESTDIR)$(schemadir)
	$(LN_S) -f /usr/share/glib-2.0/schemas/org.gnome.desktop.enums.xml $(DESTDIR)$(schemadir)
	glib-compile-schemas $(DESTDIR)$(schemadir)

uninstall-local:
	rm -f $(DESTDIR)$(schemadir)/*.xml
	rm -f $(DESTDIR)$(schemadir)/gschemas.compiled
