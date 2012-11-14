# The main file for anaconda TUI interface
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

from pyanaconda import ui
from pyanaconda.ui import common
from pyanaconda.flags import flags
import simpleline as tui
from hubs.summary import SummaryHub
from hubs.progress import ProgressHub
from spokes import StandaloneSpoke

import os

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

class ErrorDialog(tui.UIScreen):
    """Dialog screen for reporting errors to user."""

    title = _("Error")

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

    def prompt(self, args = None):
        return _("Press enter to exit.")

    def input(self, args, key):
        """This dialog is closed by any input."""
        self.close()

class YesNoDialog(tui.UIScreen):
    """Dialog screen for Yes - No questions."""

    title = _("Question")

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

    def prompt(self, args):
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

class TextUserInterface(ui.UserInterface):
    """This is the main class for Text user interface."""

    def __init__(self, storage, payload, instclass):
        """
        For detailed description of the arguments see
        the parent class.

        :param storage: storage backend reference
        :type storage: instance of pyanaconda.Storage

        :param payload: payload (usually yum) reference
        :type payload: instance of payload handler

        :param instclass: install class reference
        :type instclass: instance of install class
        """

        ui.UserInterface.__init__(self, storage, payload, instclass)
        self._app = None

    def setup(self, data):
        """Construct all the objects required to implement this interface.
           This method must be provided by all subclasses.
        """
        self._app = tui.App(u"Anaconda", yes_or_no_question = YesNoDialog)
        self._hubs = [SummaryHub, ProgressHub]

        # First, grab a list of all the standalone spokes.
        path = os.path.join(os.path.dirname(__file__), "spokes")
        actionClasses = self.getActionClasses("pyanaconda.ui.tui.spokes.%s", path, self._hubs, StandaloneSpoke)

        for klass in actionClasses:
            obj = klass(self._app, data, self.storage, self.payload, self.instclass)

            # If we are doing a kickstart install, some standalone spokes
            # could already be filled out.  In taht case, we do not want
            # to display them.
            if isinstance(obj, StandaloneSpoke) and obj.completed:
                del(obj)
                continue

            self._app.schedule_screen(obj)

    def run(self):
        """Run the interface.  This should do little more than just pass
           through to something else's run method, but is provided here in
           case more is needed.  This method must be provided by all subclasses.
        """
        self._app.run()

    ###
    ### MESSAGE HANDLING METHODS
    ###
    def showError(self, message):
        """Display an error dialog with the given message.  After this dialog
           is displayed, anaconda will quit.  There is no return value.  This
           method must be implemented by all UserInterface subclasses.

           In the code, this method should be used sparingly and only for
           critical errors that anaconda cannot figure out how to recover from.
        """
        error_window = ErrorDialog(self._app, message)
        self._app.switch_screen(error_window)

    def showDetailedError(self, message, details):
        self.showError(message + "\n\n" + details)

    def showYesNoQuestion(self, message):
        """Display a dialog with the given message that presents the user a yes
           or no choice.  This method returns True if the yes choice is selected,
           and False if the no choice is selected.  From here, anaconda can
           figure out what to do next.  This method must be implemented by all
           UserInterface subclasses.

           In the code, this method should be used sparingly and only for those
           times where anaconda cannot make a reasonable decision.  We don't
           want to overwhelm the user with choices.

           When cmdline mode is active, the default will be to answer no.
        """
        if flags.automatedInstall and not flags.ksprompt:
            # If we're in cmdline mode, just say no.
            return False
        question_window = YesNoDialog(self._app, message)
        self._app.switch_screen_modal(question_window)
        return question_window.answer
