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
Python script to ensure that translatable format strings are not present
in Glade files.

Since format substitution is language-dependent, gettext is unable to check
the validity of format string translations for strings within glade. Instead,
the format string constant, the translation substitution, and the format
substitution should all happen outside of glade. Untranslated placeholder
strings are allowable within glade.
"""

import sys
import argparse
import re

try:
    from lxml import etree
except ImportError:
    print("You need to install the python-lxml package to use check_format_string.py")
    sys.exit(1)

def check_glade_file(glade_file_path):
    global success

    with open(glade_file_path) as glade_file:
        # Parse the XML
        glade_tree = etree.parse(glade_file)

        # Check any property with translatable="yes"
        for translatable in glade_tree.xpath(".//*[@translatable='yes']"):
            # Look for % followed by an open parenthesis (indicating %(name)
            # style substitution), one of the python format conversion flags
            # (#0- +hlL), or one of the python conversion types 
            # (diouxXeEfFgGcrs)
            if re.search(r'%[-(#0 +hlLdiouxXeEfFgGcrs]', translatable.text):
                print("Translatable format string found in glade at %s:%d" % \
                        (glade_file_path, translatable.sourceline))
                success = False

if __name__ == "__main__":
    success = True
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
        check_glade_file(file_path)

    sys.exit(0 if success else 1)
