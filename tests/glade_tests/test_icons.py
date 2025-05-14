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

import os
from unittest import TestCase

from gladecheck import check_glade_files
from iconcheck import icon_exists


class CheckIcon(TestCase):
    def test_icons(self):
        """Check that all icons referenced from glade files are valid in the gnome icon theme."""
        self._test_prerequisites()
        check_glade_files(self, self._check_icons)

    def _test_prerequisites(self):
        """Check for prerequisites.

        Used in check_icons.py via tests/lib/iconcheck.py
        """
        if os.system("rpm -q adwaita-icon-theme >/dev/null 2>&1") != 0:
            raise FileNotFoundError("The 'adwaita-icon-theme' package must be installed "
                                    "to run this test.")

    def _check_icons(self, glade_tree):
        """Check that all icons referenced from glade files are valid in the gnome icon theme."""
        # Stock image names are deprecated
        stock_elements = glade_tree.xpath("//property[@name='stock' or @name='stock_id']")
        if stock_elements:
            raise AssertionError("Deprecated stock icon found at %s:%d" %
                    (stock_elements[0].base, stock_elements[0].sourceline))

        # Check whether named icons exist
        for element in glade_tree.xpath("//property[@name='icon_name']"):
            self.assertTrue(icon_exists(element.text),
                    msg="Invalid icon name %s found at %s:%d" %
                    (element.text, element.base, element.sourceline))
