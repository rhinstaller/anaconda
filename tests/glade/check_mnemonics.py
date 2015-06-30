#!/usr/bin/python3
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
# pylint: disable=interruptible-system-call

# Look for widgets with keyboard accelerators but no mnemonic


import sys
import argparse

try:
    from lxml import etree
except ImportError:
    print("You need to install the python-lxml package to run the glade checks")
    sys.exit(99)

def check_glade_file(glade_file_path):
    glade_success = True

    with open(glade_file_path) as glade_file:
        # Parse the XML
        glade_tree = etree.parse(glade_file)

        # Look for labels with use-underline=True and no mnemonic-widget
        for label in glade_tree.xpath(".//object[@class='GtkLabel' and ./property[@name='use_underline' and ./text() = 'True'] and not(./property[@name='mnemonic_widget'])]"):
            # And now filter out the cases where the label actually does have a mnemonic.
            # This list is not comprehensive, probably.

            parent = label.getparent()

            # Is the label the child of a GtkButton? The button might be pretty far up there.
            # Assume widgets names that end in "Button" are subclasses of GtkButton
            if parent.tag == 'child' and \
                    label.xpath("ancestor::object[substring(@class, string-length(@class) - string-length('Button') + 1) = 'Button']"):
                continue

            # Is the label a GtkNotebook tab?
            if parent.tag == 'child' and parent.get('type') == 'tab' and \
                    parent.getparent().get('class') == 'GtkNotebook':
                continue

            print("Label with accelerator and no mnemonic at %s:%d" % (glade_file_path, label.sourceline))
            glade_success = False

    return glade_success

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

    success = True
    for file_path in args.glade_files:
        if not check_glade_file(file_path):
            success = False

    if success:
        sys.exit(0)
    else:
        sys.exit(1)
