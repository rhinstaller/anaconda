#
# Copyright (C) 2020  Red Hat, Inc.
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
# Red Hat Author(s): Martin Kolman <mkolman@redhat.com>
#

import unittest
from pyanaconda.core.i18n import _
from pyanaconda.ui.common import sort_categories
from pyanaconda.ui.categories import SpokeCategory


class AaaCategory(SpokeCategory):

    @staticmethod
    def get_title():
        return _("FOO")

    @staticmethod
    def get_sort_order():
        return 100


class BbbCategory(SpokeCategory):

    @staticmethod
    def get_title():
        return _("BAR")

    @staticmethod
    def get_sort_order():
        return 100


class CccCategory(SpokeCategory):

    @staticmethod
    def get_title():
        return _("BAZ")

    @staticmethod
    def get_sort_order():
        return 50


class CommonCodeTestCase(unittest.TestCase):
    """Test common UI code."""

    def test_category_sorting(self):
        """Test category sorting works as expected."""

        category_list = [BbbCategory, CccCategory, AaaCategory]
        # We expect the C category to be dorted first due to sort order and
        # then A & B as they have the same sort order but A comes before B
        # on the alphabet.
        expected_category_list = [CccCategory, AaaCategory, BbbCategory]
        assert sort_categories(category_list) == expected_category_list
