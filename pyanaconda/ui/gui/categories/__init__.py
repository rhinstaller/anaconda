# Base classes for spoke categories.
#
# Copyright (C) 2011  Red Hat, Inc.
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
# Red Hat Author(s): Chris Lumens <clumens@redhat.com>
#

N_ = lambda x: x

import os.path
from pyanaconda.ui.common import collect

__all__ = ["SpokeCategory", "collect_categories"]

class SpokeCategory(object):
    """A SpokeCategory is an object used to group multiple related Spokes
       together on a hub.  It consists of a title displayed above, and then
       a two-column grid of SpokeSelectors.  Each SpokeSelector is associated
       with a Spoke subclass.  A SpokeCategory will only display those Spokes
       with a matching category attribute.

       Class attributes:

       displayOnHub  -- The Hub subclass to display this Category on.  If
                        None, this Category will be skipped.
       title         -- The title of this SpokeCategory, to be displayed above
                        the grid.
    """
    displayOnHub = None
    title = N_("DEFAULT TITLE")

    def grid(self, selectors):
        """Construct a Gtk.Grid consisting of two columns from the provided
           list of selectors.
        """
        from gi.repository import Gtk

        if len(selectors) == 0:
            return None

        row = 0
        col = 0

        g = Gtk.Grid()
        g.set_row_homogeneous(True)
        g.set_column_homogeneous(True)
        g.set_row_spacing(6)
        g.set_column_spacing(6)
        g.set_margin_bottom(12)

        for selector in selectors:
            g.attach(selector, col, row, 1, 1)

            col = int(not col)
            if col == 0:
                row += 1

        return g

def collect_categories():
    """Return a list of all category subclasses."""
    return collect("pyanaconda.ui.gui.categories.%s", os.path.dirname(__file__), lambda obj: getattr(obj, "displayOnHub", None) != None)
