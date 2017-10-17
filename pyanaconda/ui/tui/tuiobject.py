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

from pyanaconda.ui import common

from pyanaconda import iutil
from pyanaconda.constants import PASSWORD_CONFIRM_ERROR_TUI, PASSWORD_WEAK_WITH_ERROR, PASSWORD_WEAK, PW_ASCII_CHARS
from pyanaconda.constants_text import IPMI_ABORTED
from pyanaconda.i18n import _
from pyanaconda.users import validatePassword, cryptPassword

from simpleline.render.adv_widgets import ErrorDialog, GetInputScreen, GetPasswordInputScreen, YesNoDialog
from simpleline.render.screen import UIScreen, Prompt
from simpleline.render.screen_handler import ScreenHandler


def reporting_callback(message):
    """Callback used for general reporting from acceptance conditions.

    See: `AskUserInput` and `AskPassword` classes.
    """
    print(_(message))


def report_if_failed(message):
    """Decorator function to call reporting function on failed condition.

    :param message: Error message which will be printed if condition function fails.
    :type message: str
    """
    def outer_wrapper(f):
        def wrapper(*args):
            if not f(*args):
                report_func = args[-1]
                report_func(message)
                return False
            return True

        return wrapper

    return outer_wrapper


def report_check_func():
    """Decorator function to report message from condition function.

    Condition function returns the (success, error_message) tuple.
    If return_code is False send error_message to report_func and return False otherwise True.
    """
    def outer_wrapper(f):
        def wrapper(*args):
            ret, error_message = f(*args)

            if ret:
                return True

            if error_message:
                report_func = args[-1]
                report_func(error_message)

            return False

        return wrapper

    return outer_wrapper


class IpmiErrorDialog(ErrorDialog):

    def input(self, args, key):
        """Call IPMI ABORTED. Everything else will be done by original implementation."""
        iutil.ipmi_report(IPMI_ABORTED)
        super().input(args, key)


class TUIObject(UIScreen, common.UIObject):
    """Base class for Anaconda specific TUI screens. Implements the
    common pyanaconda.ui.common.UIObject interface"""

    helpFile = None

    def __init__(self, data):
        UIScreen.__init__(self)
        common.UIObject.__init__(self, data)
        self.title = u"Default title"

    @property
    def showable(self):
        return True

    @property
    def has_help(self):
        return self.helpFile is not None

    def refresh(self, args=None):
        """Put everything to display into self.window list."""
        UIScreen.refresh(self, args)


class Dialog(object):

    def __init__(self, title, conditions=None, report_func=reporting_callback):
        """Get all required information and ask user for input.

        You can use this class by itself by calling the `run()` method or in a container.
        When using in a container create this class with all required parameters and call the
        `add_to_container()` method.

        Also set user prompt to Anaconda's default.

        :param title: Name of the item which user is setting.
        :type title: str

        :param conditions: Optional acceptance conditions. If condition is not valid the
                          `wrong_input_message` is printed and user must set correct value.
        :type conditions: A function func(user_input, report_func) -> bool taking user input and returning bool.
                          See `report_func` parameter for report_func specification.

        :param report_func: Function for printing errors and warnings from conditions.
        :type report_func: Function func(message)  -- taking one argument message.
        """
        super().__init__()
        self._title = title
        self._conditions = conditions
        self._report_func = report_func

        self._user_prompt = _("Enter a new value for '%(title)s' and press %(enter)s") % {
                                # TRANSLATORS: 'title' as a title of the entry
                                "title": title,
                                # TRANSLATORS: 'enter' as the key ENTER
                                "enter": Prompt.ENTER
                               }
        self._no_separator = False

    @property
    def title(self):
        """Title of the item we want to get user input for.

        :returns: Name of the item.
        :rtype: str.
        """
        return self._title

    @title.setter
    def title(self, title):
        """Set title of the item we want to get user input for.

        :param title: Item title.
        :type title: str.
        """
        self._title = title

    @property
    def no_separator(self):
        """Print separator or hide user input as a actual screen part?

        :returns: False if separator should be printed. True if not.
        :rtype: bool. Default: False
        """
        return self._no_separator

    @no_separator.setter
    def no_separator(self, no_separator):
        """Should the separator be printed?

        :param no_separator: True to disable separator, False otherwise.
        :type no_separator: bool.
        """
        self._no_separator = no_separator

    def run(self):
        """Get input from user, run the condition functions and call setter callback at the end.

        Repeat asking user for input to the time when all the acceptance conditions will be satisfied.
        """
        screen = GetInputScreen(self._user_prompt)
        if self._conditions:
            for c in self._conditions:
                screen.add_acceptance_condition(c, self._report_func)

        screen.no_separator = self._no_separator

        ScreenHandler.push_screen_modal(screen)
        return screen.value


class PasswordDialog(Dialog):
    """Ask for user password and process it."""

    def __init__(self, title, policy, report_func=reporting_callback):
        super().__init__(title, report_func=report_func)
        self._no_separator = False
        self._policy = policy

    def run(self):
        """Get password input from user and call setter callback at the end.

        Repeat asking user for input to the time when all the password conditions will be satisfied.
        """
        password = self._ask_pass_modal(self._title, self._no_separator)
        confirm = self._ask_pass_modal("%s (confirm)" % self._title, True)

        return self._validate_password(password, confirm)

    def _ask_pass_modal(self, prompt, no_separator):
        pass_screen = GetPasswordInputScreen(prompt)
        pass_screen.no_separator = no_separator
        ScreenHandler.push_screen_modal(pass_screen)

        return pass_screen.value

    def _validate_password(self, password, confirm):
        """Validate and process user password."""
        if (password and not confirm) or (confirm and not password):
            self._report(_("You must enter your root password and confirm it by typing"
                           " it a second time to continue."))
            return None
        if password != confirm:
            self._report(_(PASSWORD_CONFIRM_ERROR_TUI))
            return None

        # If an empty password was provided, unset the value
        if not password:
            return ""

        pw_score, _status_text, pw_quality, error_message = validatePassword(password,
                                                                             user=None,
                                                                             minlen=self._policy.minlen)

        # if the score is equal to 0 and we have an error message set
        if not pw_score and error_message:
            self._report(error_message)
            return None

        if pw_quality < self._policy.minquality:
            if self._policy.strict:
                done_msg = ""
            else:
                done_msg = _("\nWould you like to use it anyway?")

            if error_message:
                error = _(PASSWORD_WEAK_WITH_ERROR) % error_message + " " + done_msg
            else:
                error = _(PASSWORD_WEAK) % done_msg

            if not self._policy.strict:
                question_window = YesNoDialog(error)
                ScreenHandler.push_screen_modal(question_window)
                if not question_window.answer:
                    return None
            else:
                self._report(error)
                return None

        if any(char not in PW_ASCII_CHARS for char in password):
            self._report(_("You have provided a password containing non-ASCII characters.\n"
                           "You may not be able to switch between keyboard layouts to login.\n"))

        return cryptPassword(password)

    def _report(self, message):
        if self._report_func:
            self._report_func(message)
