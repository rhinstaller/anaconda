#!/usr/bin/python2
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
# Author: Vratislav Podzimek <vpodzime@redhat.com>
#

"""
Simple python script checking that password GtkEntries in the given .glade files
have the visibility set to False.

"""

import argparse
import sys

try:
    from lxml import etree
except ImportError:
    print("You need to install the python-lxml package to use check_pw_visibility.py")
    sys.exit(1)

PW_ID_INDICATORS = ("pw", "password", "passwd", "passphrase")

def check_glade_file(glade_file_path):
    def check_entry(entry, fpath):
        succ = True

        entry_id = entry.attrib.get("id", "UNKNOWN ID")
        visibility_props = entry.xpath("./property[@name='visibility']")

        # no entry should have visibility specified multiple times
        if len(visibility_props) > 1:
            print("Visibility specified multiple times for the entry %s (%s)" % (entry_id, fpath))
            succ = False

        # password entry should have visibility set to False
        if any(ind in entry_id.lower() for ind in PW_ID_INDICATORS):
            if not visibility_props:
                print("Visibility not specified for the password entry %s (%s)" % (entry_id, fpath))
                succ = False
            elif visibility_props[0].text.strip() != "False":
                print("Visibility not set properly for the password entry %s (%s)" % (entry_id, fpath))
                succ = False
        # only password entries should have the visibility set to False
        elif visibility_props and visibility_props[0].text.strip() == "False":
            print("Non-password entry %s (%s) has the visibility set to False (bad id?)" % (entry_id, fpath))
            succ = False

        return succ

    succ = True
    with open(glade_file_path, "r") as glade_file:
        tree = etree.parse(glade_file)
        for entry in tree.xpath("//object[@class='GtkEntry']"):
            succ = succ and check_entry(entry, glade_file_path)

        return succ

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
        success = success and check_glade_file(file_path)

    sys.exit(0 if success else 1)
