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
Python script to check that properties in glade using Pango markup contain
valid markup.
"""

import sys
import argparse

# Import translation methods if needed
if ('-t' in sys.argv) or ('--translate' in sys.argv):
    try:
        from translatepo import translate_all
    except ImportError:
        print("Unable to load po translation module")
        sys.exit(99)

from pangocheck import markup_nodes, markup_match, markup_necessary

try:
    from lxml import etree
except ImportError:
    print("You need to install the python-lxml package to use check_markup.py")
    sys.exit(99)

class PangoElementException(Exception):
    def __init__(self, element):
        Exception.__init__(self)
        self.element = element

    def __str__(self):
        return "Invalid element %s" % self.element

def _validate_pango_markup(root):
    """Validate parsed pango markup.

       :param etree.ElementTree root: The pango markup parsed as an XML ElementTree
       :raises PangoElementException: If the pango markup contains unknown elements
    """
    if root.tag not in markup_nodes:
        raise PangoElementException(root.tag)

    for child in root:
        _validate_pango_markup(child)

def check_glade_file(glade_file_path, po_map=None):
    glade_success = True
    with open(glade_file_path) as glade_file:
        # Parse the XML
        glade_tree = etree.parse(glade_file)

        # Search for label properties on objects that have use_markup set to True
        for label in glade_tree.xpath(".//property[@name='label' and ../property[@name='use_markup']/text() = 'True']"):
            if po_map:
                try:
                    label_texts = po_map.get(label.text, label.get("context"))
                except KeyError:
                    continue
                lang_str = " for language %s" % po_map.metadata['Language']
            else:
                label_texts = (label.text,)
                lang_str = ""

            # Wrap the label text in <markup> tags and parse the tree
            for label_text in label_texts:
                try:
                    # pylint: disable=unescaped-markup
                    pango_tree = etree.fromstring("<markup>%s</markup>" % label_text)
                    _validate_pango_markup(pango_tree)

                    # Check if the markup is necessary
                    if not markup_necessary(pango_tree):
                        print("Markup could be expressed as attributes at %s%s:%d" % \
                                (glade_file_path, lang_str, label.sourceline))
                        glade_success = False
                except etree.XMLSyntaxError:
                    print("Unable to parse pango markup at %s%s:%d" % \
                            (glade_file_path, lang_str, label.sourceline))
                    glade_success = False
                except PangoElementException as px:
                    print("Invalid pango element %s at %s%s:%d" % \
                            (px.element, glade_file_path, lang_str, label.sourceline))
                    glade_success = False
                else:
                    if po_map:
                        # Check that translated markup has the same elements and attributes
                        if not markup_match(label.text, label_text):
                            print("Translated markup does not contain the same elements and attributes at %s%s:%d" % \
                                    (glade_file_path, lang_str, label.sourceline))
                            glade_success = False
    return glade_success

if __name__ == "__main__":
    parser = argparse.ArgumentParser("Check Pango markup validity")
    parser.add_argument("-t", "--translate", action='store_true',
            help="Check translated strings")
    parser.add_argument("-p", "--podir", action='store', type=str,
            metavar='PODIR', help='Directory containing po files', default='./po')
    parser.add_argument("glade_files", nargs="+", metavar="GLADE-FILE",
            help='The glade file to check')
    args = parser.parse_args(args=sys.argv[1:])

    success = True
    for file_path in args.glade_files:
        if not check_glade_file(file_path):
            success = False

    # Now loop over all of the translations
    if args.translate:
        podicts = translate_all(args.podir)
        for po_dict in podicts.values():
            for file_path in args.glade_files:
                if not check_glade_file(file_path, po_dict):
                    success = False

    sys.exit(0 if success else 1)
