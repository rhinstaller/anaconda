#
# Utility functions for the subscription module
#
# Copyright (C) 2024 Red Hat, Inc.
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

def flatten_rhsm_nested_dict(nested_dict):
    """Convert the GetAll() returned nested dict into a flat one.

    RHSM returns a nested dict with categories on top
    and category keys & values inside. This is not convenient
    for setting keys based on original values, so
    let's normalize the dict to the flat key based
    structure similar to what's used by SetAll().

    :param dict nested_dict: the nested dict returned by GetAll()
    :return: flat key/value dictionary, similar to format used by SetAll()
    :rtype: dict
    """
    flat_dict = {}
    for category_key, category_dict in nested_dict.items():
        for key, value in category_dict.items():
            flat_key = "{}.{}".format(category_key, key)
            flat_dict[flat_key] = value
    return flat_dict
