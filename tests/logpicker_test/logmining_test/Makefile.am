# tests/logpicker_test/logmining_test/Makefile.am for anaconda
#
# Copyright (C) 2010  Red Hat, Inc.
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
# Author: Tomas Mlcoch <tmlcoch@redhat.com>

EXTRA_DIST = *.py

MAINTAINERCLEANFILES = Makefile.in

ANACDIR = $(top_builddir)/pyanaconda
TESTS_ENVIRONMENT = PYTHONPATH=$(top_builddir)/tests:$(ANACDIR)/isys/.libs:$(ANACDIR):$(top_builddir):$(top_builddir)/utils

TESTS = anacondalogminer_test.py \
    dmsetupinfologminer_test.py \
    dmsetuplslogminer_test.py \
    filesystemlogminer_test.py \
    logminerbaseclass_test.py
