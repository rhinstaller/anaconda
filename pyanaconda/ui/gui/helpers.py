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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#

# This file contains abstract base classes that are specific to GUI
# functionality. See also pyanaconda.ui.helpers.

from pyanaconda.anaconda_loggers import get_module_logger

log = get_module_logger(__name__)

from abc import ABCMeta, abstractmethod

import gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gtk

from pyanaconda.core import constants
from pyanaconda.core.i18n import _
from pyanaconda.errors import NonInteractiveError
from pyanaconda.flags import flags
from pyanaconda.ui.gui.utils import timed_action
from pyanaconda.ui.helpers import InputCheck, InputCheckHandler


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
        super().__init__(parent, input_obj, run_check, data)

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

        return super().check_status


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

       It's not possible (or at least not easy) to prevent a GtkDialog from
       returning a response, so the caller of gtk_dialog_run needs to check
       whether the input is valid and decide based on that whether to destroy
       the dialog or call gtk_dialog_run again.
    """

    def __init__(self, ok_button=None):
        super().__init__()
        self._ok_button = ok_button

    def _update_check_status(self, editable, inputcheck):
        # If an OK button was provided, set it to sensitive on any change in
        # input. This way if a user changes invalid input to valid, they can
        # immediately leave the dialog. This also means that there will be a
        # period in which the user is not prented from leaving with empty input,
        # and this condition needs to be checked.
        if self._ok_button:
            self._ok_button.set_sensitive(True)

        return super()._update_check_status(editable, inputcheck)

    def set_status(self, inputcheck):
        if inputcheck.check_status in (InputCheck.CHECK_OK, InputCheck.CHECK_SILENT):
            inputcheck.input_obj.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, None)
            inputcheck.input_obj.set_icon_tooltip_text(Gtk.EntryIconPosition.SECONDARY, "")
        else:
            inputcheck.input_obj.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY,
                    "dialog-error-symbolic")
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
        super().__init__()

        self._checker = None
        self._prev_status = None
        self._password_kickstarted = False
        # return to hub logic
        self._can_go_back = False
        self._needs_waiver = False
        self._waive_clicks = 0
        # important UI object instances
        self._password_entry = None
        self._password_confirmation_entry = None
        self._password_bar = None
        self._password_label = None

    @property
    def checker(self):
        return self._checker

    # Implemented by NormalSpoke
    @abstractmethod
    def clear_info(self):
        pass

    # Implemented by GUIObject
    @abstractmethod
    def set_warning(self, msg):
        pass

    # Implemented by NormalSpoke
    @abstractmethod
    def show_warning_message(self, message):
        pass

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

    def remove_placeholder_texts(self):
        """Remove password and confirmation placeholder texts."""
        self.password_entry.set_placeholder_text("")
        self.password_confirmation_entry.set_placeholder_text("")

    @property
    def password_bar(self):
        """Password strength bar."""
        return self._password_bar

    @property
    def password_label(self):
        """Short password status label."""
        return self._password_label

    def set_password_score(self, score):
        self.password_bar.set_value(score)

    def set_password_status(self, status_message):
        self.password_label.set_text(status_message)

    @property
    def password_entry(self):
        """The password entry widget."""
        return self._password_entry

    @property
    def password(self):
        """Input to be checked.

        Content of the input field, etc.

        :returns: input to be checked
        :rtype: str
        """
        return self.password_entry.get_text()

    @property
    def password_confirmation_entry(self):
        """The password confirmation entry widget."""
        return self._password_confirmation_entry

    @property
    def password_confirmation(self):
        """Content of the input confirmation field.

        Note that not all spokes might have a password confirmation field.

        :returns: content of the password confirmation field
        :rtype: str
        """
        return self.password_confirmation_entry.get_text()

    @property
    def password_kickstarted(self):
        """Reports if the input was initialized from kickstart.

        :returns: if the input was initialized from kickstart
        :rtype: bool
        """
        return self._password_kickstarted

    @password_kickstarted.setter
    def password_kickstarted(self, value):
        self._password_kickstarted = value

    @property
    def can_go_back(self):
        return self._can_go_back

    @can_go_back.setter
    def can_go_back(self, value):
        self._can_go_back = value

    @property
    def needs_waiver(self):
        return self._needs_waiver

    @needs_waiver.setter
    def needs_waiver(self, value):
        self._needs_waiver = value

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

    def on_password_changed(self, editable, data=None):
        """Tell checker that the content of the password field changed."""
        self.checker.password.content = self.password

    def on_password_confirmation_changed(self, editable, data=None):
        """Tell checker that the content of the password confirmation field changed."""
        self.checker.password_confirmation.content = self.password_confirmation

    def try_to_go_back(self):
        """Check whether the input validation checks allow the spoke to be exited.

           Unlike NormalSpoke.on_back_clicked, this function returns a boolean value.
           Classes implementing this class should run GUISpokeInputCheckHandler.try_to_go_back,
           and if it succeeded, run NormalSpoke.on_back_clicked.
        """
        # check if we can go back
        if self.can_go_back:
            if self.needs_waiver:
                # We can proceed but need waiver.
                # - this means we can start accumulating thw waive clicks
                self.waive_clicks += 1
                # we need to have enough waive clicks to go back
                if self.waive_clicks == 1:
                    self.show_warning_message(_(constants.PASSWORD_FINAL_CONFIRM))
                elif self.waive_clicks >= 2:
                    # clear the waive clicks & any messages
                    self.waive_clicks = 0
                    self.clear_info()
                    return True
            # we can go back unconditionally
            else:
                # clear the waive clicks & any messages
                self.waive_clicks = 0
                self.clear_info()
                return True
        # we can't get back
        return False
