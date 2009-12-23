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

ISYS_SRCS = devices.c imount.c cpio.c uncpio.c lang.c \
            isofs.c linkdetect.c vio.c ethtool.c eddsupport.c iface.c \
            auditd.c log.c

dist_noinst_HEADERS = *.h

ISYS_CFLAGS = -DVERSION='"$(PACKAGE_VERSION)"' $(NFS_CFLAGS) \
              $(NETWORKMANAGER_CFLAGS) $(LIBNL_CFLAGS) $(LIBNM_GLIB_CFLAGS) \
              $(SELINUX_CFLAGS)
ISYS_LIBS   = $(RESOLV_LIBS) $(EXT2FS_LIBS) $(ZLIB_LIBS) \
              $(DEVMAPPER_LIBS) $(BLKID_LIBS) $(X11_LIBS) $(SELINUX_LIBS) \
              $(LIBNL_LIBS) $(LIBNM_GLIB_LIBS)

isysdir     = $(pkgpyexecdir)
isys_PYTHON = *.py

pkgpyexec_LTLIBRARIES = _isys.la
_isys_la_CFLAGS       = $(PYTHON_INCLUDES) $(ISYS_CFLAGS)
_isys_la_LDFLAGS      = -module -avoid-version $(PYTHON_LDFLAGS)
_isys_la_LIBADD       = $(PYTHON_LIBS) $(ISYS_LIBS)
_isys_la_SOURCES      = isys.c $(ISYS_SRCS)

noinst_LTLIBRARIES    = libisys.la
libisys_la_CFLAGS     = $(ISYS_CFLAGS)
libisys_la_LDFLAGS    = -static
libisys_la_LIBADD     = $(ISYS_LIBS)
libisys_la_SOURCES    = $(ISYS_SRCS)

MAINTAINERCLEANFILES = Makefile.in
