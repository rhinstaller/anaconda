# The base classes for Anaconda TUI Spokes
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
from pyanaconda.ui.common import Spoke, StandaloneSpoke, NormalSpoke
from pyanaconda.ui.tui.tuiobject import TUIObject
from pyanaconda.core.i18n import N_, _

from simpleline.render.widgets import Widget, CheckboxWidget

__all__ = ["NormalTUISpoke", "StandaloneSpoke", "TUISpoke"]


# Inherit abstract methods from Spoke
# pylint: disable=abstract-method
class TUISpoke(TUIObject, Widget, Spoke):
    """Base TUI Spoke class implementing the pyanaconda.ui.common.Spoke API.
       It also acts as a Widget so we can easily add it to Hub, where is shows
       as a summary box with title, description and completed checkbox.

       :param category: category this spoke belongs to
       :type category: string

       .. inheritance-diagram:: TUISpoke
          :parts: 3
    """

    def __init__(self, data, storage, payload):
        if self.__class__ is TUISpoke:
            raise TypeError("TUISpoke is an abstract class")

        TUIObject.__init__(self, data)
        Widget.__init__(self)
        Spoke.__init__(self, storage, payload)

        self.input_required = True
        self.title = N_("Default spoke title")

    @property
    def status(self):
        return _("testing status...")

    @property
    def completed(self):
        return True

    def refresh(self, args=None):
        TUIObject.refresh(self, args)

    def input(self, args, key):
        """Handle the input, the base class just forwards it to the App level."""
        return key

    def render(self, width):
        """Render the summary representation for Hub to internal buffer."""
        Widget.render(self, width)

        if self.mandatory and not self.completed:
            key = "!"
        elif self.completed:
            key = "x"
        else:
            key = " "

        # always set completed = True here; otherwise key value won't be
        # displayed if completed (spoke value from above) is False
        c = CheckboxWidget(key=key, completed=True,
                           title=_(self.title), text=self.status)
        c.render(width)
        self.draw(c)


class NormalTUISpoke(TUISpoke, NormalSpoke):
    """
       .. inheritance-diagram:: NormalTUISpoke
          :parts: 3
    """
    pass

class StandaloneTUISpoke(TUISpoke, StandaloneSpoke):
    """
       .. inheritance-diagram:: StandaloneTUISpoke
          :parts: 3
    """
    pass
