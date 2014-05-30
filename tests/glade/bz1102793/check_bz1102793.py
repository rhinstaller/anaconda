#!/usr/bin/python
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

# Check for objects that contain only a signal element, because GtkBuilder
# screws these up. This check and its associated changes can be reverted as
# soon as gtk gets its shit together.

import sys
import argparse

try:
    from lxml import etree
except ImportError:
    print("You need to install the python-lxml package to run the glade checks")
    sys.exit(99)

success = True

def main(argv):
    global success

    for glade_file in argv:
        # Look for object elements that contain a single signal child and no other children
        glade_tree = etree.parse(glade_file)

        for problem in glade_tree.xpath("//object[count(child::*) = 1 and local-name(./*) = 'signal']"):
            print("Problematic signal found at %s:%d" % (glade_file, problem.sourceline))
            success = False

if __name__ == "__main__":
    parser = argparse.ArgumentParser("Check for glade files affected by bug 1102793")

    # Ignore translation arguments
    parser.add_argument("-t", "--translate", action='store_true',
            help=argparse.SUPPRESS)
    parser.add_argument("-p", "--podir", action='store', type=str,
            metavar='PODIR', help=argparse.SUPPRESS, default='./po')

    parser.add_argument("glade_files", nargs="+", metavar="GLADE-FILE",
            help='The glade file to check')
    args = parser.parse_args(args=sys.argv[1:])

    main(args.glade_files)

    if success:
        sys.exit(0)
    else:
        sys.exit(1)
