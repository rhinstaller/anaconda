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

# This file contains abstract base classes that are specific to GUI
# functionality. See also pyanaconda.ui.helpers.

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

from abc import ABCMeta, abstractproperty, abstractmethod

import gi
gi.require_version("Gtk", "3.0")

from gi.repository import Gtk

from pyanaconda.flags import flags
from pyanaconda.ui.helpers import InputCheck, InputCheckHandler
from pyanaconda.ui.gui.utils import timed_action
from pyanaconda.i18n import _
from pyanaconda.users import validatePassword
from pyanaconda.errors import NonInteractiveError
from pyanaconda import constants

def autoinstall_stopped(reason):
    """ Reaction on stop of automatic kickstart installation

        Log why the installation stopped and raise the NonInteractiveError in
        non interactive mode.

        :param data: Kickstart data object.
        :param reason: Why the automatic kickstart installation stopped.
    """
    log.info("kickstart installation stopped for info: %s", reason)
    if not flags.ksprompt:
        raise NonInteractiveError("Non interactive installation failed: %s" % reason)

class GUIInputCheck(InputCheck):
    """ Add timer awareness to an InputCheck.

        Add a delay before running the validation function so that the
        function is not run for every keystroke. Run any pending actions
        before returning a status.
    """

    def __init__(self, parent, input_obj, run_check, data=None):
        InputCheck.__init__(self, parent, input_obj, run_check, data)

        # Add the timer here instead of decorating a method so that a new
        # TimedAction is created for every instance
        self.update_check_status = timed_action(busy_cursor=False)(self.update_check_status)

    @property
    def check_status(self):
        if self.update_check_status.timer_active:
            # The timer is hooked up to update_check_status, which takes no arguments.
            # Since the timed_action wrapper was made around the bound method of a
            # GUIInputCheck instance and not the function of a GUIInputCheck class,
            # self is already applied and update_check_status is just a regular TimedAction
            # object, not a curried function around the object.
            self.update_check_status.run_now()

        return super(GUIInputCheck, self).check_status

# Inherit abstract methods from InputCheckHandler
# pylint: disable=abstract-method
class GUIInputCheckHandler(InputCheckHandler, metaclass=ABCMeta):
    """Provide InputCheckHandler functionality for Gtk input screens.

       This class assumes that all input objects are of type GtkEditable and
       attaches InputCheck.update_check_status to the changed signal.
    """

    def _update_check_status(self, editable, inputcheck):
        inputcheck.update_check_status()

    def get_input(self, input_obj):
        return input_obj.get_text()

    def add_check(self, input_obj, run_check, data=None):
        # Use a GUIInputCheck to run the validation in a GLib timer
        checkRef = GUIInputCheck(self, input_obj, run_check, data)

        # Start a new timer on each keystroke
        input_obj.connect_after("changed", self._update_check_status, checkRef)

        # Add the InputCheck to the parent class's list of checks
        self._check_list.append(checkRef)

        return checkRef

class GUIDialogInputCheckHandler(GUIInputCheckHandler, metaclass=ABCMeta):
    """Provide InputCheckHandler functionality for Gtk dialogs.

       If an OK button is provided in the constructor, this class will
       handle setting the sensitivity of the button to match the input
       check result. A method on_ok_clicked is provided to determine whether
       the dialog can be exited, similar to on_back_clicked for spokes.

       It's not possible (or at least not easy) to prent a GtkDialog from
       returning a response, so the caller of gtk_dialog_run needs to check
       whether the input is valid and decide based on that whether to destroy
       the dialog or call gtk_dialog_run again.
    """

    def __init__(self, ok_button=None):
        GUIInputCheckHandler.__init__(self)
        self._ok_button = ok_button

    def _update_check_status(self, editable, inputcheck):
        # If an OK button was provided, set it to sensitive on any change in
        # input. This way if a user changes invalid input to valid, they can
        # immediately leave the dialog. This also means that there will be a
        # period in which the user is not prented from leaving with empty input,
        # and this condition needs to be checked.
        if self._ok_button:
            self._ok_button.set_sensitive(True)

        return super(GUIDialogInputCheckHandler, self)._update_check_status(editable, inputcheck)

    def set_status(self, inputcheck):
        if inputcheck.check_status in (InputCheck.CHECK_OK, InputCheck.CHECK_SILENT):
            inputcheck.input_obj.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, None)
            inputcheck.input_obj.set_icon_tooltip_text(Gtk.EntryIconPosition.SECONDARY, "")
        else:
            inputcheck.input_obj.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY,
                    "dialog-error")
            inputcheck.input_obj.set_icon_tooltip_text(Gtk.EntryIconPosition.SECONDARY,
                inputcheck.check_status)

        # Update the ok button sensitivity based on the check status.
        # If the result is CHECK_OK, set_sensitive(True) still needs to be
        # called, even though the changed handler above also makes the button
        # sensitive. A direct call to update_check_status may have bypassed the
        # changed signal.
        if self._ok_button:
            self._ok_button.set_sensitive(inputcheck.check_status == InputCheck.CHECK_OK)

    def on_ok_clicked(self):
        """Return whether the input validation checks allow the dialog to be exited.

           Unlike GUISpokeInputCheckHandler.on_back_clicked, it is not expected that
           subclasses will implement this method.
        """
        failed_check = next(self.failed_checks, None)

        if failed_check:
            failed_check.input_obj.grab_focus()
            return False
        else:
            return True

class GUISpokeInputCheckHandler(GUIInputCheckHandler, metaclass=ABCMeta):
    """Provide InputCheckHandler functionality for graphical spokes.

       This class implements set_status to set a message in the warning area of
       the spoke window and provides an implementation of on_back_clicked to
       prevent the user from exiting a spoke with bad input.
    """

    def __init__(self):
        GUIInputCheckHandler.__init__(self)

        # Store the previous status to avoid setting the info bar to the same
        # message multiple times
        self._prev_status = None
        self._waive_clicks = 0
        self._waive_ASCII_clicks = 0
        self._policy = None
        self._input_enabled = True

    def set_status(self, inputcheck):
        """Update the warning with the input validation error from the first
           error message.
        """
        failed_check = next(self.failed_checks_with_message, None)

        if not failed_check:
            self.clear_info()
            self._prev_status = None
        elif failed_check.check_status != self._prev_status:
            self._prev_status = failed_check.check_status
            self.clear_info()
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

    @abstractmethod
    def on_back_clicked(self, button):
        """Check whether the input validation checks allow the spoke to be exited.

           Unlike NormalSpoke.on_back_clicked, this function returns a boolean value.
           Classes implementing this class should run GUISpokeInputCheckHandler.on_back_clicked,
           and if it succeeded, run NormalSpoke.on_back_clicked.
        """
        failed_check = next(self.failed_checks, None)
        if failed_check:
            failed_check.input_obj.grab_focus()
            return False
        else:
            return True

    def check_password_confirm(self, inputcheck):
        """If the user has entered confirmation data, check whether it matches the password."""
        # Skip the check if no password is required
        if (not self.input_enabled) or self.input_kickstarted:
            result = InputCheck.CHECK_OK
        elif self.input_confirmation and (self.input != self.input_confirmation):
            result = _(constants.PASSWORD_CONFIRM_ERROR_GUI)
        else:
            result = InputCheck.CHECK_OK

        return result

    def check_password_empty(self, inputcheck):
        """Check whether a password has been specified at all.

           This check is used for both the password and the confirmation.
        """
        # If the password was set by kickstart, skip the strength check
        # pylint: disable=no-member
        if self.input_kickstarted and not self.policy.changesok:
            return InputCheck.CHECK_OK

        # Skip the check if no password is required
        if (not self.input_enabled) or self.input_kickstarted:
            return InputCheck.CHECK_OK
        # Also skip the check if the policy says that an empty password is fine
        # pylint: disable=no-member
        elif self.policy.emptyok:
            return InputCheck.CHECK_OK
        elif not self.get_input(inputcheck.input_obj):
            # pylint: disable=no-member
            if self.policy.strict:
                return _(constants.PASSWORD_EMPTY_ERROR)
            else:
                if self.waive_clicks > 1:
                    return InputCheck.CHECK_OK
                else:
                    return "%s %s" % (_(constants.PASSWORD_EMPTY_ERROR), _(constants.PASSWORD_DONE_TWICE))
        else:
            return InputCheck.CHECK_OK

    def check_user_password_strength(self, inputcheck):
        """Update the error message based on password strength.

           The password strength check can be waived by pressing "Done" twice. This
           is controlled through the self.waive_clicks counter. The counter
           is set in on_back_clicked, which also re-runs this check manually.
         """
        pw = self.input

        # Don't run any check if the password is empty - there is a dedicated check for that
        if not pw:
            return InputCheck.CHECK_OK

        # determine the password strength
        # pylint: disable=no-member
        pw_check_result = validatePassword(pw,
                                           self.input_username,
                                           minlen=self.policy.minlen,
                                           empty_ok=self.policy.emptyok)
        pw_score, status_text, pw_quality, error_message = pw_check_result
        self.set_input_score(pw_score)
        self.set_input_status(status_text)

        # Skip the check if no password is required
        if not self.input_enabled or self.input_kickstarted:
            return InputCheck.CHECK_OK

        # pylint: disable=no-member
        if pw_quality < self.policy.minquality or not pw_score or not pw:
            # If Done has been clicked twice, waive the check
            if self.waive_clicks > 1:
                return InputCheck.CHECK_OK
            elif self.waive_clicks == 1:
                if error_message:
                    return _(constants.PASSWORD_WEAK_CONFIRM_WITH_ERROR) % error_message
                else:
                    return _(constants.PASSWORD_WEAK_CONFIRM)
            else:
                # non-strict allows done to be clicked twice
                # pylint: disable=no-member
                if self.policy.strict:
                    done_msg = ""
                else:
                    done_msg = _(constants.PASSWORD_DONE_TWICE)

                if error_message:
                    return _(constants.PASSWORD_WEAK_WITH_ERROR) % error_message + " " + done_msg
                else:
                    return _(constants.PASSWORD_WEAK) % done_msg
        else:
            return InputCheck.CHECK_OK

    def check_password_ASCII(self, inputcheck):
        """Set an error message if the password contains non-ASCII characters.

           Like the password strength check, this check can be bypassed by
           pressing Done twice.
        """
        # If Done has been clicked, waive the check
        if self.waive_ASCII_clicks > 0:
            return InputCheck.CHECK_OK

        password = self.get_input(inputcheck.input_obj)
        if password and any(char not in constants.PW_ASCII_CHARS for char in password):
            return _(constants.PASSWORD_ASCII)

        return InputCheck.CHECK_OK
