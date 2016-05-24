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

from gladecheck import GladeTest
from iconcheck import icon_exists

class CheckIcon(GladeTest):
    def checkGlade(self, glade_tree):
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
