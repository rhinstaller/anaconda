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

import sys
import argparse

from collections import Counter

try:
    from lxml import etree
except ImportError:
    print("You need to install the python-lxml package to run the glade checks")
    sys.exit(99)

success = True

def main(argv):
    global success

    for glade_file in argv:
        # Parse the glade file to ensure it's well-formed
        try:
            glade_tree = etree.parse(glade_file)
        except etree.XMLSyntaxError:
            print("%s is not a valid XML file" % glade_file)
            success = False
            continue

        # Check for duplicate IDs
        # Build a Counter from a list of all ids, extracts the ones with count > 1
        # Fun fact: glade uses <col id="<number>"> in GtkListStore data, so ids
        # aren't actually unique and getting an object with a particular ID
        # isn't as simple as document.getElementById. Only check the IDs on objects.
        for glade_id in [c for c in Counter(glade_tree.xpath(".//object/@id")).most_common() \
                if c[1] > 1]:
            print("%s: ID %s appears %d times" % (glade_file, glade_id[0], glade_id[1]))
            success = False

        # Check for ID references
        # mnemonic_widget properties and action-widget elements need to refer to
        # valid object ids.
        for mnemonic_widget in glade_tree.xpath(".//property[@name='mnemonic_widget']"):
            if not glade_tree.xpath(".//object[@id='%s']" % mnemonic_widget.text):
                print("mnemonic_widget reference to invalid ID %s at line %d of %s" % \
                        (mnemonic_widget.text, mnemonic_widget.sourceline, glade_file))
                success = False

        for action_widget in glade_tree.xpath(".//action-widget"):
            if not glade_tree.xpath(".//object[@id='%s']" % action_widget.text):
                print("action-widget reference to invalid ID %s at line %d of %s" % \
                        (action_widget.text, action_widget.sourceline, glade_file))
                success = False

if __name__ == "__main__":
    parser = argparse.ArgumentParser("Check glade file validity")

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
