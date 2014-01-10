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
