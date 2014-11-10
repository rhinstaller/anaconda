# data/Makefile.am for anaconda
#
# Copyright (C) 2014  Red Hat, Inc.
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
# Author: Martin Kolman <mkolman@redhat.com>

enhelpcontentdir              = $(datadir)/anaconda/help/en-US
# The $(srcdir)/*.*ml expression matches both the *.html placeholders and *.xml help
# content files. It also works around the fact that autotools complain if the xml files
# are not present but $(srcdir)/*.xml is used.
dist_enhelpcontent_DATA       = $(srcdir)/*.*ml

MAINTAINERCLEANFILES = Makefile.in
