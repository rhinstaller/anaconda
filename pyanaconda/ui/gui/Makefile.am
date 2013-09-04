# Copyright (C) 2011, 2012  Red Hat, Inc.
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
# Author: Chris Lumens <clumens@redhat.com>

SUBDIRS = categories hubs spokes tools

MAINTAINERCLEANFILES = Makefile.in

pkgpyexecdir = $(pyexecdir)/py$(PACKAGE_NAME)
guidir       = $(pkgpyexecdir)/ui/gui
gui_PYTHON   = $(srcdir)/*.py

uidir        = $(datadir)/$(PACKAGE_NAME)/ui/
dist_ui_DATA = $(srcdir)/*.glade
