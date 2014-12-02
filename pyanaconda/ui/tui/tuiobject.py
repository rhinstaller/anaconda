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

from pyanaconda.i18n import N_, _
from pyanaconda.ui import common
from pyanaconda.ui.tui import simpleline as tui
from pyanaconda.constants_text import INPUT_PROCESSED

class ErrorDialog(tui.UIScreen):
    """Dialog screen for reporting errors to user."""

    title = N_("Error")

    def __init__(self, app, message):
        """
        :param app: the running application reference
        :type app: instance of App class

        :param message: the message to show to the user
        :type message: unicode
        """

        tui.UIScreen.__init__(self, app)
        self._message = message

    def refresh(self, args = None):
        tui.UIScreen.refresh(self, args)
        text = tui.TextWidget(self._message)
        self._window.append(tui.CenterWidget(text))
        return True

    def prompt(self, args = None):
        return _("Press enter to exit.")

    def input(self, args, key):
        """This dialog is closed by any input."""
        self.close()
        return INPUT_PROCESSED

class YesNoDialog(tui.UIScreen):
    """Dialog screen for Yes - No questions."""

    title = N_("Question")

    def __init__(self, app, message):
        """
        :param app: the running application reference
        :type app: instance of App class

        :param message: the message to show to the user
        :type message: unicode
        """

        tui.UIScreen.__init__(self, app)
        self._message = message
        self._response = None

    def refresh(self, args = None):
        tui.UIScreen.refresh(self, args)
        text = tui.TextWidget(self._message)
        self._window.append(tui.CenterWidget(text))
        self._window.append(u"")
        return True

    def prompt(self, args = None):
        return _("Please respond 'yes' or 'no': ")

    def input(self, args, key):
        if key == _("yes"):
            self._response = True
            self.close()
            return None

        elif key == _("no"):
            self._response = False
            self.close()
            return None

        else:
            return False

    @property
    def answer(self):
        """The response can be True (yes), False (no) or None (no response)."""
        return self._response

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

    def refresh(self, args = None):
        """Put everything to display into self.window list."""
        tui.UIScreen.refresh(self, args)
