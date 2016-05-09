#!/bin/sh
# Copyright (C) 2016  Red Hat, Inc.
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

# Test a project's .po files

if [ $# -ne 1 ]; then
    echo "Usage: test_projects.sh <project-list-file>"
    exit 1
fi

status=0
while read project_name branch ; do
    echo "Testing $project_name:$branch"

    podir="$(mktemp -d ${project_name}-${branch}.XXXXXX)"

    # The zanata output only matters if something goes wrong
    zanata_output="$(zanata pull --project-type gettext --project-id "$project_name" --project-version "$branch" --transdir "$podir" --url https://fedora.zanata.org/ 2>&1)"
    if [ $? -ne 0 ]; then
        echo "Zanata pull failed for $project_name:$branch"
        echo "$zanata_output"
        status=1
        rm -rf "$podir"
        continue
    fi

    # Ignore the percent-translated warnings
    python3 -W ignore -m translation_canary.translated "$podir"
    if [ $? -ne 0 ]; then
        echo "Canary test failed for $project_name:$branch"
        status=1
    else
        echo "Success: $project_name:$branch"
    fi

    rm -rf "$podir"
done < "$1"

exit "$status"
