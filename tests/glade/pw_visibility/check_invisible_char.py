#!/usr/bin/python2
#
# Copyright (C) 2015  Red Hat, Inc.
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
Check that the invisible_char in glade files is actually a char.

The invisible char is often non-ASCII and sometimes that gets clobbered.
"""

import argparse
import sys

try:
    from lxml import etree
except ImportError:
    print("You need to install the python-lxml package to use check_pw_visibility.py")
    sys.exit(1)

def check_glade_file(glade_file_path):
    succ = True

    with open(glade_file_path, "r") as glade_file:
        tree = etree.parse(glade_file)
        # Only look for entries with an invisible_char property
        for entry in tree.xpath("//object[@class='GtkEntry' and ./property[@name='invisible_char']]"):
            # Check the contents of the invisible_char property
            invis = entry.xpath("./property[@name='invisible_char']")[0]
            if len(invis.text) != 1:
                print("invisible_char at %s:%s not a character" % (glade_file_path, invis.sourceline))
                succ = False

            # If the char is '?' that's probably also bad
            if invis.text == '?':
                print("invisible_char at %s:%s is not what you want" % (glade_file_path, invis.sourceline))

            # Check that invisible_char even does anything: visibility should be False
            if not entry.xpath("./property[@name='visibility' and ./text() = 'False']"):
                print("Pointless invisible_char found at %s:%s" % (glade_file_path, invis.sourceline))
                succ = False

    return succ


if __name__ == "__main__":
    parser = argparse.ArgumentParser("Check that invisible character properties are set correctly")

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
