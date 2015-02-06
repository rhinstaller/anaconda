#!/usr/bin/python2
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
#

"""
Check that widgets that implement GtkScrollable are not placed within a
GtkViewport. If a widget knows how to scroll itself we probably don't want
to add an extra layer.
"""

import argparse
import sys

try:
    from lxml import etree
except ImportError:
    print("You need to install the python-lxml package to use check_pw_visibility.py")
    sys.exit(1)

# I guess we could look at the introspected classes and see if they implement the Scrollable
# interface but that sounds like kind of a pain
SCROLLABLES = ["GtkIconView", "GtkLayout", "GtkTextView", "GtkToolPalette",
               "GtkTreeView", "GtkViewport"]

def check_glade_file(glade_file_path):
    glade_success = True
    with open(glade_file_path) as glade_file:
        # Parse the XML
        glade_tree = etree.parse(glade_file)

        # Look for something like:
        # <object class="GtkViewport">
        #   <child>
        #      <object class="GtkTreeView">
        for scrollable in SCROLLABLES:
            for element in glade_tree.xpath(".//object[@class='GtkViewport']/child/object[@class='%s']" % scrollable):
                glade_success = False
                print("%s contained in GtkViewport at %s:%d" % (scrollable, glade_file_path,
                                                                element.sourceline))
    return glade_success

if __name__ == "__main__":
    parser = argparse.ArgumentParser("Check that password entries have visibility set to False")

    # Ignore translation arguments
    parser.add_argument("-t", "--translate", action='store_true',
            help=argparse.SUPPRESS)
    parser.add_argument("-p", "--podir", action='store', type=str,
            metavar='PODIR', help=argparse.SUPPRESS, default='./po')

    parser.add_argument("glade_files", nargs="+", metavar="GLADE-FILE",
            help='The glade file to check')
    args = parser.parse_args(args=sys.argv[1:])

    success = True
    for file_path in args.glade_files:
        if not check_glade_file(file_path):
            success = False

    sys.exit(0 if success else 1)
