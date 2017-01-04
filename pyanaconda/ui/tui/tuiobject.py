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
import sys
from pyanaconda import iutil, constants
from pyanaconda.i18n import N_, _, C_
from pyanaconda.ui import common
from pyanaconda.ui.tui import simpleline as tui

class ErrorDialog(tui.UIScreen):
    """Dialog screen for reporting errors to user."""

    title = N_("Error")

    def __init__(self, app, message):
        """
        :param app: the running application reference
        :type app: instance of App class

        :param message: the message to show to the user
        :type message: str
        """

        tui.UIScreen.__init__(self, app)
        self._message = message

    def refresh(self, args=None):
        tui.UIScreen.refresh(self, args)
        text = tui.TextWidget(self._message)
        self._window += [tui.CenterWidget(text), ""]
        return True

    def prompt(self, args=None):
        return tui.Prompt(_("Press %s to exit") % tui.Prompt.ENTER)

    def input(self, args, key):
        """This dialog is closed by any input.

        And causes the program to quit.
        """
        iutil.ipmi_report(constants.IPMI_ABORTED)
        sys.exit(1)

class PasswordDialog(tui.UIScreen):
    """Dialog screen for password input."""

    title = N_("Password")

    def __init__(self, app, device):
        """
        :param app: the running application reference
        :type app: instance of App class
        """

        tui.UIScreen.__init__(self, app)
        self._device = device
        self._message = "You must enter your LUKS passphrase to decrypt device %s" % device
        self._password = None

    def refresh(self, args=None):
        tui.UIScreen.refresh(self, args)
        text = tui.TextWidget(self._message)
        self._window += [tui.CenterWidget(text), ""]
        return True

    def prompt(self, args=None):
        self._password = self.app.raw_input(_("Passphrase: "), hidden=True)
        if not self._password:
            return None
        else:
            # this may seem innocuous, but it's really a giant hack; we should
            # not be calling close() from prompt(), but the input handling code
            # in the TUI is such that without this very simple workaround, we
            # would be forever pelting users with a prompt to enter their pw
            self.close()

    @property
    def answer(self):
        """The response can be None (no response) or the password entered."""
        return self._password

    def input(self, args, key):
        if key:
            self._password = key
            self.close()
            return True
        else:
            return False

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

    def refresh(self, args=None):
        tui.UIScreen.refresh(self, args)
        text = tui.TextWidget(self._message)
        self._window += [tui.CenterWidget(text), ""]
        return True

    def prompt(self, args=None):
        return tui.Prompt(_("Please respond '%(yes)s' or '%(no)s'") % {
            # TRANSLATORS: 'yes' as positive reply
            "yes": C_('TUI|Spoke Navigation', 'yes'),
            # TRANSLATORS: 'no' as negative reply
            "no": C_('TUI|Spoke Navigation', 'no')
        })

    def input(self, args, key):
        # TRANSLATORS: 'yes' as positive reply
        if key == C_('TUI|Spoke Navigation', 'yes'):
            self._response = True
            self.close()
            return None

        # TRANSLATORS: 'no' as negative reply
        elif key == C_('TUI|Spoke Navigation', 'no'):
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

    def refresh(self, args=None):
        """Put everything to display into self.window list."""
        tui.UIScreen.refresh(self, args)
