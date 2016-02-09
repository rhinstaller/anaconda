#!/bin/bash
#
# Copyright (C) 2014  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Chris Lumens <clumens@redhat.com>

# TODO: If all gui tests are properly annotated with a skipIf decorator
# this file can be dropped and the tests executed by nosetests_root.sh

function doit() {
    ARGS="-s \
          -v \
          --nologcapture \
          --process-timeout=1200 \
          --processes=1          \
          --tc=resultsdir:$(mktemp -d --tmpdir=$top_srcdir/tests autogui-results-XXXXXX)"

    export LC_ALL=C # translations confuse Dogtail

    if [ -z "$1" ]; then
        nosetests-3.5 ${ARGS} ${GUI_TESTS:-$top_srcdir/tests/gui/test_*.py}
    else
        nosetests-3.5 ${ARGS} "${1}" ${GUI_TESTS:-$top_srcdir/tests/gui/test_*.py}
    fi
}

if [ -z "$top_srcdir" ]; then
    top_srcdir="$(dirname "$0")/.."
fi

# this script needs absolute paths
export top_srcdir=`readlink -f $top_srcdir`
if [ ! -z "$top_builddir" ]; then
    export top_builddir=`readlink -f $top_builddir`
fi
. ${top_srcdir}/tests/testenv.sh

if ! rpm -q python3-nose-testconfig &> /dev/null; then
    echo "test_config plugin is not available; exiting."
    exit 99
fi

# Have to be root to run this test, as it requires creating disk iamges.
if [ ${EUID} != 0 ]; then
   echo "You must be root to run the GUI tests; skipping."
   exit 77
fi

if [ -z "${DISPLAY}" ]; then
   echo "DISPLAY is not set; skipping."
   exit 77
fi

# We need SELinux Permissive or Disabled, see rhbz#1276376
if [ `getenforce` == "Enforcing" ]; then
   echo "SELinux is in Enforcing mode; skipping."
   exit 77
fi

# in case we want coverage support configure
# python to start coverage for all processes
if [ ! -z "$COVERAGE_PROCESS_START" ]; then
    ROOT_SITE_PACKAGES=`python3 -m site --user-site`
    mkdir -p "$ROOT_SITE_PACKAGES"
    if [ ! -f "$ROOT_SITE_PACKAGES/usercustomize.py" ]; then
        cp "$top_srcdir/tests/usercustomize.py" "$ROOT_SITE_PACKAGES"
    fi
fi

if [[ "${TEST_ANACONDA_ARGS}" != "" ]]; then
    EXTRA="--tc=anacondaArgs:\"${TEST_ANACONDA_ARGS}\""
elif [[ $# != 0 ]]; then
    EXTRA="--tc=anacondaArgs:\"$*\""
else
    EXTRA=""
fi

# execute the tests
doit "${EXTRA}"
