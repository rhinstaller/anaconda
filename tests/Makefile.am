# Makefile.am for anaconda tests
#
# Copyright (C) 2013  Red Hat, Inc.
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
# Author: David Shea <dshea@redhat.com>

# This Makefile is non-recursive so that all tests can easily be run with the
# same python environment. $top_srcdir and $top_builddir are added to the
# environment so that tests can get their bearings. Tests need to be aware that
# they may be run from within an arbitrary working directory.
# 
# While automake claims that it doesn't support wildcards anywhere, they really
# mean it with the parallel test harness. Rather than reverting back to the
# serial harness, all of the nosetests-based checks will be run serially by
# nosetests.sh. This script can be run in parallel with the other test scripts,
# such as pylint.
#
# nosetests will be run for any python files found in a directory matching *_tests

AM_TESTS_ENVIRONMENT = top_srcdir="$(top_srcdir)" top_builddir="$(top_builddir)" ; . $(srcdir)/testenv.sh ;
TEST_EXTENSIONS = .sh

dist_check_DATA = pylint/pylint-false-positives

# Test scripts need to be listed both here and in TESTS
dist_check_SCRIPTS = accelerators/check_accelerators.py \
		     accelerators/run_check_accelerators.sh \
		     nosetests.sh \
		     pylint/runpylint.sh \
		     testenv.sh \
		     gettext/gettext_warnings.sh \
		     $(srcdir)/*_tests/*.py

TESTS = nosetests.sh \
	pylint/runpylint.sh \
	gettext/gettext_warnings.sh \
	accelerators/run_check_accelerators.sh
