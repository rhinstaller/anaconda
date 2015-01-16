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
from gi.repository import Gtk

from pyanaconda.ui.helpers import InputCheck, InputCheckHandler

# Inherit abstract methods from InputCheckHandler
# pylint: disable=abstract-method
class GUIInputCheckHandler(InputCheckHandler):
    """Provide InputCheckHandler functionality for Gtk input screens.

       This class assumes that all input objects are of type GtkEditable and
       attaches InputCheck.update_check_status to the changed signal.
    """

    __metaclass__ = ABCMeta

    def _update_check_status(self, editable, inputcheck):
        inputcheck.update_check_status()

    def get_input(self, input_obj):
        return input_obj.get_text()

    def add_check(self, input_obj, run_check, data=None):
        checkRef = InputCheckHandler.add_check(self, input_obj, run_check, data)
        input_obj.connect_after("changed", self._update_check_status, checkRef)
        return checkRef

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
           Classes implementing this class should run GUISpokeInputCheckHandler.on_back_clicked,
           and if it succeeded, run NormalSpoke.on_back_clicked.
        """
        failed_check = next(self.failed_checks, None)

        if failed_check:
            failed_check.input_obj.grab_focus()
            return False
        else:
            return True
