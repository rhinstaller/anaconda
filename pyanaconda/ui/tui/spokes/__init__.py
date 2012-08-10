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
# Red Hat Author(s): Martin Sivak <msivak@redhat.com>
#
from .. import simpleline as tui
from pyanaconda.ui.tui.tuiobject import TUIObject
from pyanaconda.ui.common import Spoke, StandaloneSpoke, NormalSpoke, PersonalizationSpoke, collect
import os

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

__all__ = ["TUISpoke", "StandaloneSpoke", "NormalSpoke", "PersonalizationSpoke",
           "collect_spokes", "collect_categories"]

class TUISpoke(TUIObject, tui.Widget, Spoke):
    """Base TUI Spoke class implementing the pyanaconda.ui.common.Spoke API.
    It also acts as a Widget so we can easily add it to Hub, where is shows
    as a summary box with title, description and completed checkbox.

    :param title: title of this spoke
    :type title: unicode

    :param category: category this spoke belongs to
    :type category: string
    """

    title = _("Default spoke title")
    category = u""

    def __init__(self, app, data, storage, payload, instclass):
        TUIObject.__init__(self, app, data)
        tui.Widget.__init__(self)
        Spoke.__init__(self, data, storage, payload, instclass)

    @property
    def status(self):
        return _("testing status...")

    @property
    def completed(self):
        return True

    def refresh(self, args = None):
        TUIObject.refresh(self, args)
        return True

    def input(self, args, key):
        """Handle the input, the base class just forwards it to the App level."""
        return key

    def render(self, width):
        """Render the summary representation for Hub to internal buffer."""
        tui.Widget.render(self, width)
        c = tui.CheckboxWidget(completed = self.completed, title = self.title, text = self.status)
        c.render(width)
        self.draw(c)

class StandaloneTUISpoke(TUISpoke, StandaloneSpoke):
    pass

class NormalTUISpoke(TUISpoke, NormalSpoke):
    pass

class PersonalizationTUISpoke(TUISpoke, PersonalizationSpoke):
    pass

def collect_spokes(category):
    """Return a list of all spoke subclasses that should appear for a given
       category.
    """
    return collect("pyanaconda.ui.tui.spokes.%s", os.path.dirname(__file__), lambda obj: hasattr(obj, "category") and obj.category != None and obj.category == category)

def collect_categories():
    classes = collect("pyanaconda.ui.tui.spokes.%s", os.path.dirname(__file__), lambda obj: hasattr(obj, "category") and obj.category != None and obj.category != "")
    categories = set([c.category for c in classes])
    return categories
