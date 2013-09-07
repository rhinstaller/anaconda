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
#
# Author: Kalev Lember <kalevlember@gmail.com>

welcomedir              = $(datadir)/$(PACKAGE_NAME)/gnome
dist_welcome_DATA       = fedora-welcome.desktop install-button.png
dist_welcome_SCRIPTS    = fedora-welcome

EXTRA_DIST = fedora-welcome.desktop.in

CLEANFILES = fedora-welcome.desktop

MAINTAINERCLEANFILES = Makefile.in

@INTLTOOL_DESKTOP_RULE@
