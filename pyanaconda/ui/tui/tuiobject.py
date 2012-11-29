# base TUIObject for Anaconda TUI
#
# Copyright (C) 2012  Red Hat, Inc.
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

from pyanaconda.ui import common
import simpleline as tui

class TUIObject(tui.UIScreen, common.UIObject):
    """Base class for Anaconda specific TUI screens. Implements the
    common pyanaconda.ui.common.UIObject interface"""

    title = u"Default title"

    def __init__(self, app, data):
        tui.UIScreen.__init__(self, app)
        common.UIObject.__init__(self, data)

    @property
    def showable(self):
        return True

    def teardown(self):
        pass

    def initialize(self):
        """This method gets called whenever Hub or UserInterface prepares
        all found objects for use. It is called only once and has no direct
        connection to rendering."""
        pass

    def refresh(self, args = None):
        """Put everything to display into self.window list."""
        tui.UIScreen.refresh(self, args)
