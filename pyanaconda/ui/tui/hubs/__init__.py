# The base classes for Anaconda TUI Hubs
#
# Copyright (C) (2012)  Red Hat, Inc.
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
# Red Hat Author(s): Martin Sivak <msivak@redhat.com>
#
from pyanaconda.ui.tui import simpleline as tui
from pyanaconda.ui.tui.tuiobject import TUIObject
from pyanaconda.ui import common

from pyanaconda.i18n import _, C_, N_

class TUIHub(TUIObject, common.Hub):
    """Base Hub class implementing the pyanaconda.ui.common.Hub interface.
    It uses text based categories to look for relevant Spokes and manages
    all the spokes it finds to have the proper category.

    :param categories: list all the spoke categories to be displayed in this Hub
    :type categories: list of strings

    :param title: title for this Hub
    :type title: unicode

    """

    categories = []
    title = N_("Default HUB title")

    def __init__(self, app, data, storage, payload, instclass):
        TUIObject.__init__(self, app, data)
        common.Hub.__init__(self, storage, payload, instclass)

        self._spokes = {}     # holds spokes referenced by their class name
        self._keys = {}       # holds spokes referenced by their user input key
        self._spoke_count = 0

    def setup(self, environment="anaconda"):
        cats_and_spokes = self._collectCategoriesAndSpokes()
        categories = cats_and_spokes.keys()

        for c in sorted(categories, key=lambda c: c.title):

            for spokeClass in sorted(cats_and_spokes[c], key=lambda s: s.title):
                # Check if this spoke is to be shown in anaconda
                if not spokeClass.should_run(environment, self.data):
                    continue

                spoke = spokeClass(self.app, self.data, self.storage, self.payload, self.instclass)

                if spoke.showable:
                    spoke.initialize()
                else:
                    del spoke
                    continue

                if spoke.indirect:
                    continue

                self._spoke_count += 1
                self._keys[self._spoke_count] = spoke
                self._spokes[spokeClass.__name__] = spoke

        # only schedule the hub if it has some spokes
        return self._spoke_count != 0

    def refresh(self, args = None):
        """This methods fills the self._window list by all the objects
        we want shown on this screen. Title and Spokes mostly."""
        TUIObject.refresh(self, args)

        def _prep(i, w):
            number = tui.TextWidget("%2d)" % i)
            return tui.ColumnWidget([(3, [number]), (None, [w])], 1)

        # split spokes to two columns
        left = [_prep(i, w) for i,w in self._keys.items() if i % 2 == 1]
        right = [_prep(i, w) for i,w in self._keys.items() if i % 2 == 0]

        c = tui.ColumnWidget([(39, left), (39, right)], 2)
        self._window.append(c)

        return True

    def input(self, args, key):
        """Handle user input. Numbers are used to show a spoke, the rest is passed
        to the higher level for processing."""

        try:
            number = int(key)
            self.app.switch_screen_with_return(self._keys[number])
            return None

        except (ValueError, KeyError):
            # If we get a continue, check for unfinished spokes.  If unfinished
            # don't continue
            # TRANSLATORS: 'c' to continue
            if key == C_('TUI|Spoke Navigation', 'c'):
                for spoke in self._spokes.values():
                    if not spoke.completed and spoke.mandatory:
                        print(_("Please complete all spokes before continuing"))
                        return False
            return key
