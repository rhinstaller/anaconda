# utils/Makefile.am for anaconda
#
# Copyright (C) 2009-2013  Red Hat, Inc.
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

utilsdir            = $(libexecdir)/$(PACKAGE_NAME)
utils_PROGRAMS      = dd_list dd_extract

dd_list_LDADD = $(RPM_LIBS) $(LIBARCHIVE_LIBS)
dd_list_SOURCES = rpmutils.c dd_list.c rpmutils.h dd_utils.h

dd_extract_LDADD = $(LIBARCHIVE_LIBS) $(RPM_LIBS)
dd_extract_SOURCES = rpmutils.c dd_extract.c rpmutils.h dd_utils.h

MAINTAINERCLEANFILES = Makefile.in
