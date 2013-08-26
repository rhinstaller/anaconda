#!/usr/bin/python
#
# Copyright (C) 2013  Red Hat, Inc.
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
import re
import os.path

try:
    from lxml import etree
except ImportError:
    print("You need to install the python-lxml package to use check_accelerators.py")
    sys.exit(1)

accel_re = re.compile(r'_(?P<accel>.)')

def check_glade(glade_filename):
    success = True
    with open(glade_filename) as glade_file:
        # Parse the XML
        glade_tree = etree.parse(glade_file)

        # Assume that each top-level object is a separate context
        for interface_object in glade_tree.xpath("/interface/object"):
            accels = {}

            # Select the label properties of objects whose use_underline
            # property is true.
            # NB: This is why we can't use python's builtin etree
            for label in interface_object.xpath(".//property[@name='label' and ../property[@name='use_underline']/text() = 'True']"):
                match = accel_re.search(label.text)
                if match:
                    accel = match.group('accel').lower()
                    if accel in accels:
                        # Check for an exception comment
                        prev = label.getprevious()
                        if (prev is not None) and (prev.tag == etree.Comment) and \
                                prev.text.strip().startswith('check_accelerators:'):
                            continue

                        print("Accelerator collision for key %s in %s:%s\n    line %d: %s\n    line %d: %s" %\
                                (accel, os.path.normpath(glade_filename), interface_object.attrib['id'],
                                    accels[accel].sourceline, accels[accel].text, 
                                    label.sourceline, label.text))
                        success = False
                    else:
                        accels[accel] = label
    return success

def main(argv=sys.argv):
    parser = argparse.ArgumentParser("Check for duplicated accelerators")
    parser.add_argument("glade_files", nargs="+", metavar="GLADE-FILE",
            help='The glade file to check')
    args = parser.parse_args(args=argv)

    success = True
    for glade_file in args.glade_files:
        if not check_glade(glade_file):
            success = False
    return success

if __name__ == "__main__":
    result = main(sys.argv[1:])

    if result:
        sys.exit(0)
    else:
        sys.exit(1)
