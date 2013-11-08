# liveinst/console.apps/Makefile.am for anaconda
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

if IS_LIVEINST_ARCH
consoledir        = $(sysconfdir)/security/console.apps
dist_console_DATA = liveinst
endif
#
# Files generated for gettext need to be included in the distribution
EXTRA_DIST = $(srcdir)/liveinst.h
$(srcdir)/liveinst.h: $(srcdir)/liveinst
	@$(MAKE) -C $(top_builddir)/po $(abs_top_srcdir)/$(subdir)/$$(basename $@)

CLEANFILES = *.h
MAINTAINERCLEANFILES = Makefile.in
