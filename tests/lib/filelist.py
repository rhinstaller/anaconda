#
# filelist.py: method for determining which files to check
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

import os
import subprocess

def testfilelist(filterfunc=None):
    """A generator function for the list of file names to check.

       If the check is run from a git work tree, the method returns a list
       of files known to git. Otherwise, it returns a list of every file
       beneath $top_srcdir.

       top_srcdir must be set in the environment.

       filterfunc, if provided, is a function that takes a filename as an
       argument and returns True for files that should be included in the
       file list. For example, something like lambda x: fnmatch(x, '*.py')
       could be used to match only filenames that end in .py.
    """

    if os.path.isdir(os.path.join(os.environ["top_srcdir"], ".git")):
        output = subprocess.check_output(["git", "ls-files", "-c", os.environ["top_srcdir"]])
        filelist = output.split("\n")
    else:
        filelist = (os.path.join(path, testfile) \
                        for path, _dirs, files in os.walk(os.environ["top_srcdir"]) \
                        for testfile in files)

    for f in filelist:
        if not filterfunc or filterfunc(f):
            yield f
