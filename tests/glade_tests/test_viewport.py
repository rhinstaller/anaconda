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

# I guess we could look at the introspected classes and see if they implement the Scrollable
# interface but that sounds like kind of a pain
SCROLLABLES = ["GtkIconView", "GtkLayout", "GtkTextView", "GtkToolPalette",
               "GtkTreeView", "GtkViewport"]


class CheckViewport(TestCase):
    def test_viewport(self):
        """Check that widgets that implement GtkScrollable are not in a viewport."""
        check_glade_files(self, self._check_viewport)

    def _check_viewport(self, glade_tree):
        """Check that widgets that implement GtkScrollable are not in a viewport.

           If a widgets knows how to scroll itself we do not want to add an extra layer.
        """

        # Look for something like:
        # <object class="GtkViewport">
        #   <child>
        #      <object class="GtkTreeView">
        for scrollable in SCROLLABLES:
            for element in glade_tree.xpath(".//object[@class='GtkViewport']/child/object[@class='%s']" % scrollable):
                raise AssertionError("%s contained in GtkViewport at %s:%d" %
                        (scrollable, element.base, element.sourceline))
