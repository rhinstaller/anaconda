#!/bin/sh
# Shell functions for use by anaconda tests
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
# Author: David Shea <dshea@redhat.com>

# Print a list of files to test on stdout
# Takes filter arguments identical to the find utility, for example
# findtestfiles -name '*.py'. Note that pruning directories will not
# work since find is passed a list of filenames as the path arguments.
findtestfiles()
{
    # If the test is being run from a git work tree, use a list of all files
    # known to git
    if [ -d "${top_srcdir}/.git" ]; then
        findpath=$(git ls-files -c "${top_srcdir}")
    # Otherwise list everything under $top_srcdir
    else
        findpath="${top_srcdir} -type f"
    fi

    find $findpath "$@"
}
