#
# Copyright (C) 2021  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Martin Kolman <mkolman@redhat.com>
#

import unittest

from pyanaconda.modules.subscription.utils import flatten_rhsm_nested_dict


class FlattenRHSMNestedDictTestCase(unittest.TestCase):
    """Test the RHSM nested dict flattening function."""

    def test_empty_dict(self):
        """Test the flattening function can handle an empty dict being passed."""
        self.assertEqual(flatten_rhsm_nested_dict({}), {})

    def test_nested_dict(self):
        """Test the flattening function can handle a nested dict being passed."""
        self.assertEqual(flatten_rhsm_nested_dict({"foo": {"bar": "baz"}}), {"foo.bar": "baz"})