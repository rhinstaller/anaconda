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

from pyanaconda.core import util, constants
from pyanaconda import input_checking
from pyanaconda.core.i18n import _
from pyanaconda.core.users import crypt_password

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # This dialog is run by the error handler. The handler
        # might be triggered by an error from a different thread.
        # It is possible that we are already asking for a user
        # input when we decide to show the dialog. That would
        # violate the concurrency check, so disable it.
        self.input_manager.skip_concurrency_check = True

    def input(self, args, key):
        """Call IPMI ABORTED. Everything else will be done by original implementation."""
        util.ipmi_report(constants.IPMI_ABORTED)
        super().input(args, key)


class TUIObject(UIScreen, common.UIObject):
    """Base class for Anaconda specific TUI screens. Implements the
    common pyanaconda.ui.common.UIObject interface"""

    def __init__(self, data):
        UIScreen.__init__(self)
        common.UIObject.__init__(self, data)
        self.title = "Default title"

    @property
    def showable(self):
        return True

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

    def __init__(self, title, policy_name,
                 report_func=reporting_callback,
                 process_func=crypt_password,
                 secret_type=constants.SecretType.PASSWORD,
                 message=None):
        super().__init__(title, report_func=report_func)
        self._no_separator = False
        self._policy = input_checking.get_policy(policy_name)
        self._secret_type = secret_type
        self._process_password = process_func
        self._dialog_message = message
        self._username = ""

    @property
    def username(self):
        return self._username

    @username.setter
    def username(self, new_username):
        self._username = new_username

    def run(self):
        """Get password input from user and call setter callback at the end.

        Repeat asking user for input to the time when all the password conditions will be satisfied.
        """
        password = self._ask_pass_modal(self._get_password_prompt(), self._no_separator)
        confirm = self._ask_pass_modal(self._get_confim_prompt(), True)
        return self._validate_password(password, confirm)

    def _get_password_prompt(self):
        if not self._dialog_message:
            return self._title

        return f"{self._dialog_message}\n\n{self._title}"

    def _get_confim_prompt(self):
        return f"{self._title} (confirm)"

    def _ask_pass_modal(self, prompt, no_separator):
        pass_screen = GetPasswordInputScreen(prompt)
        pass_screen.no_separator = no_separator
        ScreenHandler.push_screen_modal(pass_screen)

        return pass_screen.value

    def _validate_password(self, password, confirm):
        """Validate and process user password."""
        if password != confirm:
            self._report(_(constants.SECRET_CONFIRM_ERROR_TUI[self._secret_type]))
            return None

        # If an empty password was provided, unset the value
        if not password:
            return ""

        # prepare a password validation request
        password_check_request = input_checking.PasswordCheckRequest()
        password_check_request.password = password
        password_check_request.password_confirmation = ""
        password_check_request.policy = self._policy
        # configure username for checking
        password_check_request.username = self.username

        # validate the password
        password_check = input_checking.PasswordValidityCheck()
        password_check.run(password_check_request)

        # if the score is equal to 0 and we have an error message set
        if not password_check.result.password_score and password_check.result.error_message:
            self._report(password_check.result.error_message)
            return None

        if password_check.result.password_quality < self._policy.min_quality:
            if self._policy.is_strict:
                done_msg = ""
            else:
                done_msg = _("\nWould you like to use it anyway?")

            if password_check.result.error_message:
                weak_prefix = _(constants.SECRET_WEAK_WITH_ERROR[self._secret_type])
                error = f"{weak_prefix} {password_check.result.error_message} {done_msg}"
            else:
                weak_prefix = _(constants.SECRET_WEAK[self._secret_type])
                error = f"{weak_prefix} {done_msg}"

            if not self._policy.is_strict:
                question_window = YesNoDialog(error)
                ScreenHandler.push_screen_modal(question_window)
                if not question_window.answer:
                    return None
            else:
                self._report(error)
                return None

        if any(char not in constants.PW_ASCII_CHARS for char in password):
            self._report(_(constants.SECRET_ASCII[self._secret_type]))

        return self._process_password(password)

    def _report(self, message):
        if self._report_func:
            self._report_func(message)
