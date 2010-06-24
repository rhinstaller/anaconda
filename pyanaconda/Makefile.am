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

SUBDIRS = booty installclasses isys iw textw storage 

MAINTAINERCLEANFILES = Makefile.in

# anaconda Python code
pkgpyexecdir    = $(pyexecdir)/py$(PACKAGE_NAME)
anacondadir     = $(pkgpyexecdir)
anaconda_PYTHON = *.py
pkgpyexec_LTLIBRARIES = xutils.la

xutils_la_CFLAGS      = $(PYTHON_INCLUDES) $(GDK_CFLAGS) -fno-strict-aliasing
xutils_la_LDFLAGS     = -module -avoid-version $(PYTHON_LDFLAGS) $(GDK_LDFLAGS)
xutils_la_LIBADD      = $(PYTHON_LIBS) $(GDK_LIBS)
xutils_la_SOURCES     = xutils.c

