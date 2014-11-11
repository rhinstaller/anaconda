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
    ARGS="-s \
          -v \
          --nologcapture \
          --process-timeout=1200 \
          --processes=2 \
          --tc=resultsdir:$(mktemp -d --tmpdir=$(pwd) autogui-results-XXXXXX) \
          --tc=liveImage:$1"

    if [ -z "$2" ]; then
        nosetests ${ARGS} ${GUI_TESTS:-outside}
    else
        nosetests ${ARGS} "${2}" ${GUI_TESTS:-outside}
    fi
}

# We require the test_config plugin for nose, which is not currently packaged
# but is installable via pip.
if [ -z "$(nosetests -p | grep test_config)" ]; then
    echo "test_config plugin is not available; exiting."
    exit 99
fi

# Have to be root to run this test, as it requires creating disk iamges.
if [ ${EUID} != 0 ]; then
   echo "You must be root to run the GUI tests; skipping."
   exit 77
fi

# The livecd location can come from one of two different places:
# (1) $TEST_LIVECD, if this script is being called from "make check"
# (2) The command line, if this script is being called directly.
if [[ "${TEST_LIVECD}" != "" ]]; then
    LIVECD=${TEST_LIVECD}
elif [[ $# != 0 ]]; then
    LIVECD=$1
    shift
else
    echo "usage: $0 <livecd.iso> [anaconda args...]"
    exit 1
fi

if [ ! -e "${LIVECD}" ]; then
    echo "Required live CD image does not exist."
    exit 2
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
    ( cd gui && doit ${LIVECD} "${EXTRA}" )
elif [ -d outside ]; then
    doit ${LIVECD} "${EXTRA}"
else
    echo "Could not find test contents"
    exit 3
fi
