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

from abc import ABCMeta, abstractproperty, abstractmethod

import gi
gi.require_version("Gtk", "3.0")

from gi.repository import Gtk

from pyanaconda.ui.helpers import InputCheck, InputCheckHandler
from pyanaconda.ui.gui.utils import timed_action

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

    @abstractmethod
    def on_back_clicked(self, window):
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
