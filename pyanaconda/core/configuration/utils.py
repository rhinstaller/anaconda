#
# Copyright (C) 2021 Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from pyanaconda.core.string import split_in_two


def split_name_and_attributes(value):
    """Split the given string into a name and a dictionary of attributes.

    :param value: a string of the type 'name (attr1 val1, attr2, ...)'
    :return: a name and a dictionary of attributes
    """
    # Parse the line.
    name, raw_attrs = split_in_two(value.strip())

    # Split the attribute definitions.
    raw_attrs = raw_attrs.strip("()").split(",")

    # Strip the attribute definitions.
    raw_attrs = map(str.strip, raw_attrs)

    # Skip empty strings (split always returns
    # at least one item, an empty string).
    raw_attrs = filter(None, raw_attrs)

    # Split the name and the value of each attribute.
    raw_attrs = dict(map(split_in_two, raw_attrs))

    return name, raw_attrs
