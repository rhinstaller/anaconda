#!/usr/bin/python3
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

from unittest import TestCase

from gladecheck import check_glade_files
from lxml import etree
from pocketlint.pangocheck import markup_match, markup_necessary, markup_nodes


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


class CheckMarkup(TestCase):
    def test_markup(self):
        """Check the validity of Pango markup."""
        check_glade_files(self, self._check_markup)

    def _check_markup(self, glade_tree):
        """Check the validity of Pango markup."""
        lang = glade_tree.getroot().get("lang")
        if lang:
            lang_str = " for language %s" % lang
        else:
            lang_str = ""

        # Search for label properties on objects that have use_markup set to True
        for label in glade_tree.xpath(".//property[@name='label' and ../property[@name='use_markup']/text() = 'True']"):
            # Wrap the label text in <markup> tags and parse the tree
            try:
                # pylint: disable=unescaped-markup,c-extension-no-member
                pango_tree = etree.fromstring("<markup>%s</markup>" % label.text)
                _validate_pango_markup(pango_tree)

                # Check if the markup is necessary
                self.assertTrue(markup_necessary(pango_tree),
                        msg="Markup %s could be expressed as attributes at %s%s:%d" %
                            (label.text, label.base, lang_str, label.sourceline))
            # pylint: disable=c-extension-no-member
            except etree.XMLSyntaxError as xx:
                raise AssertionError(
                    "Unable to parse pango markup %s at %s%s:%d" %
                    (label.text, label.base, lang_str, label.sourceline)
                ) from xx
            except PangoElementException as px:
                raise AssertionError(
                    "Invalid pango element %s at %s%s:%d" %
                    (px.element, label.base, lang_str, label.sourceline)
                ) from px

            # If this is a translated node, check that the translated markup
            # has the same elements and attributes as the original.
            orig_markup = label.get("original_text")
            if orig_markup:
                self.assertTrue(markup_match(label.text, orig_markup),
                        msg="Translated markup %s does not contain the same elements and attributes at %s%s:%d" %
                                (label.text, label.base, lang_str, label.sourceline))
