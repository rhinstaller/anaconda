# Abstract base classes for GUI classes
#
# Copyright (C) 2014  Red Hat, Inc.
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
# Red Hat Author(s): David Shea <dshea@redhat.com>
#

# This file contains abstract base classes that are specific to GUI
# functionality. See also pyanaconda.ui.helpers.

import logging
log = logging.getLogger("anaconda")

from abc import ABCMeta, abstractproperty, abstractmethod
from gi.repository import Gtk

from pyanaconda.ui.helpers import InputCheck, InputCheckHandler
from pyanaconda.i18n import _
from pyanaconda.users import validatePassword, PasswordCheckRequest
from pyanaconda import constants

# Inherit abstract methods from InputCheckHandler
# pylint: disable=abstract-method
class GUIInputCheckHandler(InputCheckHandler):
    """Provide InputCheckHandler functionality for Gtk input screens.

       This class assumes that all input objects are of type GtkEditable and
       attaches InputCheck.update_check_status to the changed signal.
    """

    __metaclass__ = ABCMeta

    def __init__(self):
        super(GUIInputCheckHandler, self).__init__()
        self._policy = None
        self._input_enabled = True

    @property
    def policy(self):
        """Input checking policy.

        :returns: the input checking policy
        """
        return self._policy

    @policy.setter
    def policy(self, input_policy):
        """Set the input checking policy.

        :param input_policy: the input checking policy
        """
        self._policy = input_policy

    @property
    def input_enabled(self):
        """Is the input we are checking enabled ?

        For example on the User spoke it is possible to disable the password input field.

        :returns: is the input we are checking enabled
        :rtype: bool
        """
        return self._input_enabled

    @input_enabled.setter
    def input_enabled(self, value):
        self._input_enabled = value

    @property
    def input_kickstarted(self):
        """Reports if the input was initialized from kickstart.

        :returns: if the input was initialized from kickstart
        :rtype: bool
        """
        return False

    @property
    def input_username(self):
        """A username corresponding to the input (if any).

        :returns: username corresponding to the input or None
        :rtype: str on None
        """
        return None

    @property
    def input(self):
        """Input to be checked.

        Content of the input field, etc.

        :returns: input to be checked
        :rtype: str
        """
        return None

    @property
    def input_confirmation(self):
        """Content of the input confirmation field.

        Note that not all spokes might have a password confirmation field.

        :returns: content of the password confirmation field
        :rtype: str
        """
        pass

    @property
    def name_of_input(self):
        """Name of the input to be used called in warnings and error messages.

        For example:
        "%s contains non-ASCII characters"
        can be customized to:
        "Password contains non-ASCII characters"
        or
        "Passphrase contains non-ASCII characters"

        :returns: name of the input being checked
        :rtype: str
        """
        return _(constants.NAME_OF_PASSWORD)

    @property
    def name_of_input_plural(self):
        """Plural name of the input to be used called in warnings and error messages.

        :returns: plural name of the input being checked
        :rtype: str
        """
        return _(constants.NAME_OF_PASSWORD_PLURAL)

    def set_input_score(self, score):
        """Set input quality score.

        :param int score: input quality score
        """
        pass

    def set_input_status(self, status_message):
        """Set input quality status message.

        :param str status: input quality status message
        """
        pass

    def _update_check_status(self, editable, inputcheck):
        inputcheck.update_check_status()

    def get_input(self, input_obj):
        return input_obj.get_text()

    def add_check(self, input_obj, run_check, data=None):
        checkRef = InputCheckHandler.add_check(self, input_obj, run_check, data)
        input_obj.connect_after("changed", self._update_check_status, checkRef)
        return checkRef

    # checks

    def check_password_confirm(self, inputcheck):
        """If the user has entered confirmation data, check whether it matches the password."""
        # Skip the check if no password is required
        if (not self.input_enabled) or self.input_kickstarted:
            result = InputCheck.CHECK_OK
        elif self.input_confirmation and (self.input != self.input_confirmation):
            result = _(constants.PASSWORD_CONFIRM_ERROR_GUI) % {"passwords": self.name_of_input_plural}
        else:
            result = InputCheck.CHECK_OK
        return result

    def check_password_strength(self, inputcheck):
        """Update password check status based on password strength.

           On spokes the password strength check can be waived by pressing "Done" twice.
           This is controlled through the self.waive_clicks counter.
           The counter is set in on_back_clicked, which also re-runs this check manually.
         """
        pw = self.input

        # Don't run any check if the password is empty - there is a dedicated check for that
        if not pw:
            # Also update the score & status if the password is empty,
            # as it might have been deleted and the previous score and status
            # would still be shown.
            self.set_input_score(0)
            self.set_input_status(_(constants.PASSWORD_STATUS_EMPTY))
            return InputCheck.CHECK_OK

        # determine password strength
        request = PasswordCheckRequest(password=pw,
                                       username=self.input_username,
                                       minimum_length=self.policy.minlen,
                                       empty_ok=self.policy.emptyok,
                                       name_of_password=self.name_of_input)

        result = validatePassword(check_request=request)
        self.set_input_score(result.password_score)
        self.set_input_status(result.status_text)

        # Skip the check if no password is required
        if not self.input_enabled or self.input_kickstarted:
            return InputCheck.CHECK_OK

        # pylint: disable=no-member
        if result.password_quality < self.policy.minquality or not result.password_score or not pw:
            return self.handle_weak_password(result)
        else:
            return InputCheck.CHECK_OK

    def handle_weak_password(self, result):
        if result.length_ok:
            return _(constants.PASSWORD_WEAK_WITH_ERROR) % {"password": self.name_of_input,
                                                            "error_message": result.error_message}
        else:
            return "%s." % result.error_message

    def check_password_ASCII(self, inputcheck):
        """Set an error message if the password contains non-ASCII characters."""
        password = self.get_input(inputcheck.input_obj)
        if password and any(char not in constants.PW_ASCII_CHARS for char in password):
            return _(constants.PASSWORD_ASCII) % {"password": self.name_of_input}
        return InputCheck.CHECK_OK


class GUIDialogInputCheckHandler(GUIInputCheckHandler):
    """Provide InputCheckHandler functionality for Gtk dialogs.

       This class provides a helper method for setting an error message
       on an entry field. Implementors of this class must still provide
       a set_status method in order to control the sensitivty of widgets or
       ignore activated signals.
    """

    __metaclass__ = ABCMeta

    @abstractmethod
    def set_status(self, inputcheck):
        if inputcheck.check_status in (InputCheck.CHECK_OK, InputCheck.CHECK_SILENT):
            inputcheck.input_obj.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, None)
            inputcheck.input_obj.set_icon_tooltip_text(Gtk.EntryIconPosition.SECONDARY, "")
        else:
            inputcheck.input_obj.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY,
                    "dialog-error")
            inputcheck.input_obj.set_icon_tooltip_text(Gtk.EntryIconPosition.SECONDARY,
                inputcheck.check_status)

class GUISpokeInputCheckHandler(GUIInputCheckHandler):
    """Provide InputCheckHandler functionality for graphical spokes.

       This class implements set_status to set a message in the warning area of
       the spoke window and provides an implementation of on_back_clicked to
       prevent the user from exiting a spoke with bad input.
    """

    __metaclass__ = ABCMeta

    def __init__(self):
        GUIInputCheckHandler.__init__(self)

        # Store the previous status to avoid setting the info bar to the same
        # message multiple times
        self._prev_status = None

    def set_status(self, inputcheck):
        """Update the warning with the input validation error from the first
           error message.
        """
        failed_check = next(self.failed_checks_with_message, None)

        self.clear_info()
        if failed_check:
            self.set_warning(failed_check.check_status)

    # Implemented by GUIObject
    @abstractmethod
    def clear_info(self):
        pass

    # Implemented by GUIObject
    @abstractmethod
    def set_warning(self, msg):
        pass

    # Implemented by GUIObject
    @abstractproperty
    def window(self):
        pass

    @abstractmethod
    def on_back_clicked(self, window):
        """Check whether the input validation checks allow the spoke to be exited.

           Unlike NormalSpoke.on_back_clicked, this function returns a boolean value.
           Classes implementing this class should run GUISpokePasswordCheckHandler.on_back_clicked,
           and if it succeeded, run NormalSpoke.on_back_clicked.
        """
        failed_check = next(self.failed_checks, None)

        if failed_check:
            failed_check.input_obj.grab_focus()
            return False
        else:
            return True

class GUISpokePasswordCheckHandler(GUISpokeInputCheckHandler):
    """Extend GUISpokeInputCheckHandler with password checking functionality for graphical spokes.

    This class adds methods needed for efficiently check that passwords comply with current
    passowrd policy in graphical spokes, that can be used by different spokes to avoid code duplication.
    """

    __metaclass__ = ABCMeta

    def __init__(self):
        GUISpokeInputCheckHandler.__init__(self)
        self._password_required = False
        self._waive_clicks = 0
        self._waive_ASCII_clicks = 0

    @property
    def password_required(self):
        """If password is required to be set for the current screen.

        In general this local on-screen represents stuff like the
        "require password" tick-box on the user spoke.

        :returns: if password is required for the current screen
        :rtype: bool
        """
        return self._password_required

    @password_required.setter
    def password_required(self, password_needed):
        """Set if password is required for the current screen.

        :param bool password_is_required: if pasword needs to be non-empty
        """
        self._password_required = password_needed

    @property
    def waive_clicks(self):
        """Number of waive clicks the user has done to override an input check.

        :returns: number of waive clicks
        :rtype: int
        """
        return self._waive_clicks

    @waive_clicks.setter
    def waive_clicks(self, clicks):
        """Set number of waive clicks.

        :param int clicks: number of waive clicks
        """
        self._waive_clicks = clicks

    @property
    def waive_ASCII_clicks(self):
        """Number of waive clicks the user has done to override the ASCII input check.

        :returns: number of ASCII check waive clicks
        :rtype: int
        """
        return self._waive_ASCII_clicks

    @waive_ASCII_clicks.setter
    def waive_ASCII_clicks(self, clicks):
        """Set number of ASCII check waive clicks.

        :param int clicks: number of ASCII check waive clicks
        """
        self._waive_ASCII_clicks = clicks

    def check_password_empty(self, inputcheck):
        """Check whether a password has been specified at all.

           This check is used for both the password and the confirmation.
        """
        # If the password was set by kickstart, skip the check.
        # pylint: disable=no-member
        if self.input_kickstarted and not self.policy.changesok:
            return InputCheck.CHECK_OK

        # Skip the check if no password is required
        if (not self.input_enabled) or self.input_kickstarted:
            return InputCheck.CHECK_OK
        # Also skip the check if the policy says that an empty password is fine
        # and non-empty password is not required by the screen.
        # pylint: disable=no-member
        elif self.policy.emptyok and not self.password_required:
            return InputCheck.CHECK_OK
        elif not self.get_input(inputcheck.input_obj):
            # pylint: disable=no-member
            if self.policy.strict or self.password_required:
                return _(constants.PASSWORD_EMPTY_ERROR) % {"password": self.name_of_input}
            else:
                if self.waive_clicks > 1:
                    return InputCheck.CHECK_OK
                else:
                    return _(constants.PASSWORD_EMPTY_ERROR) % {"password": self.name_of_input} + " " + _(constants.PASSWORD_DONE_TWICE)
        else:
            return InputCheck.CHECK_OK

    def check_password_ASCII(self, inputcheck):
        """Set an error message if the password contains non-ASCII characters.

           Like the password strength check, this check can be bypassed by
           pressing Done twice.
        """
        password = self.get_input(inputcheck.input_obj)
        if password and any(char not in constants.PW_ASCII_CHARS for char in password):
            # If Done has been clicked, waive the check
            if self.waive_ASCII_clicks > 1:
                return InputCheck.CHECK_OK
            elif self.waive_ASCII_clicks == 1:
                error_message = _(constants.PASSWORD_ASCII) % {"password": self.name_of_input}
                return "%s %s" % (error_message, _(constants.PASSWORD_FINAL_CONFIRM))
            else:
                error_message = _(constants.PASSWORD_ASCII) % {"password": self.name_of_input}
                return "%s %s" % (error_message, _(constants.PASSWORD_DONE_TWICE))

        return InputCheck.CHECK_OK

    def handle_weak_password(self, result):
        # If Done has been clicked twice, waive the check
        if self.waive_clicks > 1:
            return InputCheck.CHECK_OK
        elif self.waive_clicks == 1:
            if result.error_message:
                if result.length_ok:
                    main_message = _(constants.PASSWORD_WEAK_WITH_ERROR) % {"password": self.name_of_input,
                                                                            "error_message": result.error_message}
                    suffix = _(constants.PASSWORD_FINAL_CONFIRM)
                    return main_message + " " + suffix
                else:
                    return "%s." % result.error_message + " " + _(constants.PASSWORD_FINAL_CONFIRM)
            else:
                main_message = _(constants.PASSWORD_WEAK) % {"password": self.name_of_input}
                return main_message + " " + _(constants.PASSWORD_FINAL_CONFIRM)
        else:
            # non-strict allows done to be clicked twice
            if result.error_message:
                if result.length_ok:
                    if self.policy.strict:
                        combined_error_message = result.error_message
                    else:
                        combined_error_message = result.error_message + " " + _(constants.PASSWORD_DONE_TWICE)

                    return _(constants.PASSWORD_WEAK_WITH_ERROR) % {"password": self.name_of_input,
                                                                    "error_message": combined_error_message}
                else:
                    if self.policy.strict:
                        return "%s." % result.error_message
                    else:
                        return "%s." % result.error_message + " " + _(constants.PASSWORD_DONE_TWICE)
            else:
                main_message = _(constants.PASSWORD_WEAK) % {"password": self.name_of_input}
                return main_message + " " + _(constants.PASSWORD_DONE_TWICE)
