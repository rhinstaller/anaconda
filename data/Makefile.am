# data/Makefile.am for anaconda
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

SUBDIRS = command-stubs gtk-4.0 liveinst systemd pam pixmaps window-manager dbus conf.d profile.d

CLEANFILES = *~

dist_pkgdata_DATA          = interactive-defaults.ks \
			     tmux.conf \
			     anaconda-gtk.css

helpdir               = $(datadir)/$(PACKAGE_NAME)
dist_help_DATA        = anaconda_options.txt

configdir           = $(sysconfdir)/$(PACKAGE_NAME)
dist_config_DATA    = anaconda.conf

MAINTAINERCLEANFILES = Makefile.in
