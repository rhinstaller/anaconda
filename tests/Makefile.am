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

# This Makefile is non-recursive so that all tests can easily be run with the
# same python environment. $top_srcdir and $top_builddir are added to the
# environment so that tests can get their bearings. Tests need to be aware that
# they may be run from within an arbitrary working directory.
#
# While automake claims that it doesn't support wildcards anywhere, they really
# mean it with the parallel test harness. Rather than reverting back to the
# serial harness, all of the unit tests based checks will be run serially by
# unit_tests.sh. This script can be run in parallel with the other test scripts,
# such as pylint.
#
# unit tests will be run for any python files with prefix "test" found in the
# tests/unit_tests directory

AM_TESTS_ENVIRONMENT = top_srcdir="$(abs_top_srcdir)" top_builddir="$(abs_top_builddir)" ; . $(srcdir)/testenv.sh ;
TEST_EXTENSIONS = .sh

# files necessary for running the tests (make ci) from a tarball
EXTRA_DIST = README.rst usercustomize.py

# Also add translation-canary for canary_tests.sh
EXTRA_DIST += $(top_srcdir)/translation-canary/translation_canary/*.py \
	      $(top_srcdir)/translation-canary/translation_canary/*/*.py

UNIT_TESTS_PATTERN ?= ""

# Test scripts need to be listed both here and in TESTS
dist_check_SCRIPTS = \
	$(srcdir)/glade_tests/*.py \
	$(srcdir)/lib/*.py \
	unit_tests/unit_tests.sh \
	rpm_tests/rpm_tests.sh \
	pylint/runpylint \
	cppcheck/runcppcheck.sh \
	testenv.sh \
	$(srcdir)/gettext_tests/*.py \
	gettext_tests/canary_tests.sh \
	$(srcdir)/*_tests/*.py \
	$(srcdir)/*_tests/*/*.py \
	$(srcdir)/*_tests/*/*/*.py \
	$(srcdir)/*_tests/*/*/*/*.py \
	$(srcdir)/unit_tests/*_tests/*.py \
	shellcheck/*.sh \
	ruff/run_ruff.sh

# TODO: Return back pylint/runpylint.py when it works on python 3.12
TESTS = \
	cppcheck/runcppcheck.sh \
	gettext_tests/click.py \
	gettext_tests/style_guide.py \
	gettext_tests/contexts.py \
	gettext_tests/canary_tests.sh \
	glade_tests/glade_tests.sh \
	shellcheck/run_shellcheck.sh \
	ruff/run_ruff.sh \
	pylint/runpylint.py \
	unit_tests/unit_tests.sh

clean-local:
	-rm -rf pylint/.pylint.d
