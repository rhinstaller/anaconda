# isys/Makefile.am for anaconda
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
# Author: David Cantrell <dcantrell@redhat.com>

pkgpyexecdir = $(pyexecdir)/py$(PACKAGE_NAME)

dist_noinst_HEADERS = $(srcdir)/*.h

isysdir     = $(pkgpyexecdir)/isys
isys_PYTHON = $(srcdir)/*.py

pkgpyexec_LTLIBRARIES = _isys.la
_isys_la_CFLAGS       = $(PYTHON_CFLAGS)
_isys_la_LDFLAGS      = -module -avoid-version
_isys_la_LIBADD       = $(PYTHON_LIBS)
_isys_la_SOURCES      = isys.c

auditddir             = $(libexecdir)/$(PACKAGE_NAME)
auditd_PROGRAMS       = auditd
auditd_SOURCES        = auditd.c
auditd_CFLAGS         = $(SELINUX_CFLAGS)
auditd_LDFLAGS        = -laudit

MAINTAINERCLEANFILES = Makefile.in
