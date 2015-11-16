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

function doit() {
    export NOSE_RESULTS_DIR=$(mktemp -d --tmpdir=$(pwd) autogui-results-XXXXXX)
    ARGS="-s \
          -v \
          --nologcapture \
          --process-timeout=1200 \
          --processes=1          \
          --tc=resultsdir:$NOSE_RESULTS_DIR"

    export LC_ALL=C # translations confuse Dogtail

    if [ -z "$1" ]; then
        nosetests-3.5 ${ARGS} ${GUI_TESTS:-./test_*.py}
    else
        nosetests-3.5 ${ARGS} "${1}" ${GUI_TESTS:-./test_*.py}
    fi
}

if [ -z "$top_srcdir" ]; then
    echo "*** top_srcdir must be set"
    exit 99
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

if [[ "${TEST_ANACONDA_ARGS}" != "" ]]; then
    EXTRA="--tc=anacondaArgs:\"${TEST_ANACONDA_ARGS}\""
elif [[ $# != 0 ]]; then
    EXTRA="--tc=anacondaArgs:\"$*\""
else
    EXTRA=""
fi

# If we're being called from "make check", we will be outside the gui test directory.
# Unfortunately, everything is written assuming that's where we will be.  So cd there.
if [ -d gui ]; then
    ( cd gui && doit "${EXTRA}" )
else
    doit "${EXTRA}"
fi
