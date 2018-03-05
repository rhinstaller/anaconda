# dbus/Makefile.am for anaconda
#
# Copyright (C) 2017  Red Hat, Inc.
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
# Author(s):  Vendula Poncova <vponcova@redhat.com>
#			  Jiri Konecny <jkonecny@redhat.com>

MAINTAINERCLEANFILES = Makefile.in

dbusservicesdir = $(datadir)/$(PACKAGE_NAME)/dbus/services
dist_dbusservices_DATA = $(srcdir)/*.service

dbusconfigdir = $(datadir)/$(PACKAGE_NAME)/dbus/confs
dist_dbusconfig_DATA = $(srcdir)/org.fedoraproject.Anaconda*.conf

dbusmaindir = $(datadir)/$(PACKAGE_NAME)/dbus
dist_dbusmain_DATA = $(srcdir)/anaconda-bus.conf
