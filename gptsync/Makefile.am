# gptsync/Makefile.am for anaconda
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

COMMON_SRCS      = lib.c os_unix.c
noinst_HEADERS   = gptsync.h syslinux_mbr.h

if IS_GPTSYNC_ARCH
sbin_PROGRAMS    = gptsync showpart

gptsync_CFLAGS   = -DPROGNAME=gptsync
gptsync_SOURCES  = gptsync.c $(COMMON_SRCS)

showpart_CFLAGS  = -DPROGNAME=showpart
showpart_SOURCES = showpart.c $(COMMON_SRCS)
endif

EXTRA_DIST       = README

MAINTAINERCLEANFILES = Makefile.in
