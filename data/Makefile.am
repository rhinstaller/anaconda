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
# Author: Martin Sivak <msivak@redhat.com>

SUBDIRS = bootdisk command-stubs icons liveinst pixmaps systemd ui

EXTRA_DIST = lang-table
CLEANFILES = *~ lang-names 

udevdir               = /lib/udev/rules.d
dist_udev_DATA        = 70-anaconda.rules

langdir               = $(datadir)/$(PACKAGE_NAME)
lang_DATA             = lang-names
dist_lang_DATA        = lang-table

if IS_S390
shareddir             = $(datadir)/$(PACKAGE_NAME)
dist_shared_SCRIPTS   = linuxrc.s390
endif

MAINTAINERCLEANFILES = Makefile.in

lang-names: lang-table
	PYTHONPATH="$(top_srcdir)/pyanaconda" $(PYTHON) ../scripts/getlangnames.py > lang-names
