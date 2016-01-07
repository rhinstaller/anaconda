#!/bin/sh -e
#
# xgettext_werror.sh: Run xgettext and actually do something with the warnings
#
# xgettext prints out warnings for certain problems in translatable strings,
# such as format strings that cannot be translated due to position-based
# parameters. These warnings generally indicate something that needs to be
# addressed before the strings can be submitted for translation. This script
# exits with a status of 1 so that the warnings are not ignored as they scroll
# by in pages of build output.
#
# This script should be used in place of xgettext when rebuilding the .pot file,
# e.g. by setting XGETTEXT in po/Makevars.
#
# Copyright (C) 2015  Red Hat, Inc.
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
# Red Hat Author(s): David Shea <dshea@redhat.com>

returncode=0

# Collect the output from xgettext. If xgettext fails, treat that as a failure
# Make sure that "warning:" doesn't get translated
xgettext_output="$(LC_MESSAGES=C xgettext "$@" 2>&1)" || returncode=$?

# Look for warnings
if echo "$xgettext_output" | fgrep -q "warning: "; then
    returncode=1
fi

# Print the output and return
echo "$xgettext_output"
exit $returncode
