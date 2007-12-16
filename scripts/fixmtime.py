#!/usr/bin/python
#
# fixmtime.py
#
# Copyright (C) 2007  Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

"""Walks path given on the command line for .pyc and .pyo files, changing
the mtime in the header to 0, so it will match the .py file on the cramfs"""

import os
import sys
import getopt

debug = 0

def usage():
    print 'usage: %s /path/to/walk/and/fix' %sys.argv[0]
    sys.exit(1)

def visit(arg, d, files):
    for filen in files:
        if not (filen.endswith('.pyc') or filen.endswith('.pyo')):
            continue
        path = os.sep.join((d, filen))
        #print 'fixing mtime', path
        f = open(path, 'r+')
        f.seek(4)
        f.write('\0\0\0\0')
        f.close()

if __name__ == '__main__':
    (args, extra) = getopt.getopt(sys.argv[1:], '', "debug")

    if len(extra) < 1:
        usage()

    for arg in args:
        if arg == "--debug":
            debug = 1

    dir = extra[0]

    if not os.path.isdir(dir):
        usage()

    os.path.walk(dir, visit, None)

