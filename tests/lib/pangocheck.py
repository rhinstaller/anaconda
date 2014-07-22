#
# pangocheck.py: data and methods for checking pango markup strings
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

import re
from collections import Counter

__all__ = ["markup_nodes", "is_markup", "markup_match"]

# "a" isn't actually pango markup, but GtkLabel uses it
markup_nodes = ["markup", "a", "b", "big", "i", "s", "span", "sub", "sup", "small", "tt", "u"]

# Check to see if a string looks like Pango markup, no validation
def is_markup(test_string):
    return any(re.search(r'<\s*%s(\s|>)' % node_type, test_string)
            for node_type in markup_nodes)

# Verify that the translation of a markup string looks more or less like the original
def markup_match(orig_markup, xlated_markup):
    # Look for tags. Create a count of each kind of tag and a list of attributes.
    # "Don't parse XML with regular expressions" I can hear you saying, but we're
    # not trying to match elements, just pull tag-like substrings out of the string.
    # Figuring out if tags are closed or in the right order is someone else's job.
    def _parse_markup(markup_string):
        name_count = Counter()
        attr_count = Counter()

        for tag in re.findall(r'<[^>]*>', markup_string):
            # Treat everything up to the first space, / or > as the element name
            (name, rest) = re.match(r'<([^\s/>]*)(.*)>', tag).groups()
            name_count[name] += 1

            # Strip the / from the rest of the tag, if present
            if rest.endswith('/'):
                rest = rest[:-1]

            # Make a list of attributes that need to be contained in the other string
            attr_count.update(rest.split())

        return (name_count, attr_count)

    (name_count1, attr_count1) = _parse_markup(orig_markup)
    (name_count2, attr_count2) = _parse_markup(xlated_markup)

    name_list1 = sorted(name_count1.elements())
    name_list2 = sorted(name_count2.elements())
    attr_list1 = sorted(attr_count1.elements())
    attr_list2 = sorted(attr_count2.elements())

    return (name_list1 == name_list2) and (attr_list1 == attr_list2)

# Check that the markup is needed at all.
# The input is a parsed ElementTree of the string '<markup>pango markup goes here</markup>'
# The markup is unnecessary if the only markup in the string surrounds the entire rest of
# the string, meaning that the pango attributes apply to the entire string, and thus
# could be expressed using attribute lists. For example, strings like:
#   <b>Bold text</b>
# or
#   <span foreground="grey"><i>colorful</i></span>
# but not strings like:
#   <span size="small">This string contains <b>internal</b> markup</span>
# that contain markup that must be passed to the translators.
#
# This function returns True if the markup is necessary and False if the markup
# can be discarded and expressed as attribute lists.
def markup_necessary(markup_tree):
    # If the element has no children at all, there is no markup inside and the
    # markup is unnecessary.
    if not len(markup_tree):
        return False

    # If there is more than one child, the markup is necessary
    if len(markup_tree) > 1:
        return True

    # QUICK NOTE FOR PEOPLE EXPECTING ElementTree TO ACT KINDA LIKE DOM 'CUZ LOL
    # ElementTree is kind of weird with respect to handling multiple text children
    # of an Element node. element.text is the text leading up to the first element
    # child, and element[child_idx].tail is the text following the child node that
    # is actually a child of element but isn't a property of element because Python
    # is crazy.
    #
    # A string like "<markup>word1<i>word2</i>word3<empty/>word4</markup>" will result in
    #   tree == <Element 'markup' ...>
    #   tree.text == 'word1'
    #   tree[0] == <Element 'i' ...>
    #   tree[0].text == 'word2'
    #   tree[0].tail == 'word3'
    #   tree[1] == <Element 'empty' ...>
    #   tree[1].text == None
    #   tree[1].text == 'word4'
    #
    # So elements that contain text before a child markup element will have
    # element.text is not None. Elements that have text after a child element
    # will have .tail on that child set to not None.

    # If .text is set, there is text before the child node, as in
    # <span>text <b>child</b></span>
    # and the markup is necessary
    if markup_tree.text:
        return True

    # If the child (we already know there's only one) has .tail set, then
    # there is text between the close of the child and the end of the element
    # and the markup is necessary
    if markup_tree[0].tail:
        return True

    # Recurse on the child node
    return markup_necessary(markup_tree[0])
