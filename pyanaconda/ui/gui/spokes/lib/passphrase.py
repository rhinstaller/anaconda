# Dialog for creating new encryption passphrase
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
# Red Hat Author(s): David Lehman <dlehman@redhat.com>
#

import gi
gi.require_version("Gtk", "3.0")

from gi.repository import Gtk

from pyanaconda.ui.helpers import InputCheck
from pyanaconda.ui.gui import GUIObject
from pyanaconda.ui.gui.helpers import GUIInputCheckHandler
from pyanaconda.i18n import _
from pyanaconda import constants

import logging
log = logging.getLogger("anaconda")

__all__ = ["PassphraseDialog"]

class PassphraseDialog(GUIObject, GUIInputCheckHandler):
    builderObjects = ["passphrase_dialog"]
    mainWidgetName = "passphrase_dialog"
    uiFile = "spokes/lib/passphrase.glade"

    def __init__(self, data):
        GUIObject.__init__(self, data)
        GUIInputCheckHandler.__init__(self)

        self._confirm_entry = self.builder.get_object("confirm_pw_entry")
        self._passphrase_entry = self.builder.get_object("passphrase_entry")

        self._save_button = self.builder.get_object("passphrase_save_button")

        self._strength_bar = self.builder.get_object("strength_bar")
        self._strength_label = self.builder.get_object("strength_label")

        self._passphrase_warning_image = self.builder.get_object("passphrase_warning_image")
        self._passphrase_warning_label = self.builder.get_object("passphrase_warning_label")

        # Set the offset values for the strength bar colors
        self._strength_bar.add_offset_value("low", 2)
        self._strength_bar.add_offset_value("medium", 3)
        self._strength_bar.add_offset_value("high", 4)

        # Configure the password policy, if available. Otherwise use defaults.
        self.policy = self.data.anaconda.pwpolicy.get_policy("luks")
        if not self.policy:
            self.policy = self.data.anaconda.PwPolicyData()

        # This will be set up later.
        self.passphrase = ""

        # check that the content of the passphrase field & the conformation field are the same
        self._confirm_check = self.add_check(self._confirm_entry, self.check_password_confirm)
        # check password strength
        self._strength_check = self.add_check(self._passphrase_entry, self.check_password_strength)
        # check if the passphrase contains non-ascii characters
        self._ascii_check = self.add_check(self._passphrase_entry, self.check_password_ASCII)

    @property
    def input(self):
        return self._passphrase_entry.get_text()

    @property
    def input_confirmation(self):
        return self._confirm_entry.get_text()

    @property
    def name_of_input(self):
        return _(constants.NAME_OF_PASSPHRASE)

    @property
    def name_of_input_plural(self):
        return _(constants.NAME_OF_PASSPHRASE_PLURAL)

    def refresh(self):
        super(PassphraseDialog, self).refresh()

        # disable input methods for the passphrase Entry widgets
        self._passphrase_entry.set_property("im-module", "")
        self._confirm_entry.set_property("im-module", "")

        # initialize with the previously set passphrase
        self.passphrase = self.data.autopart.passphrase

        if not self.passphrase:
            self._save_button.set_sensitive(False)

        self._passphrase_entry.set_text(self.passphrase)
        self._confirm_entry.set_text(self.passphrase)

        # Update the check states and force a status update
        self._confirm_check.update_check_status()
        self._strength_check.update_check_status()
        self._ascii_check.update_check_status()
        self.set_status(None)

    def run(self):
        self.refresh()
        self.window.show_all()
        rc = self.window.run()
        self.window.destroy()
        return rc

    def set_input_score(self, score):
        self._strength_bar.set_value(score)

    def set_input_status(self, status_text):
        self._strength_label.set_text(status_text)

    def set_status(self, inputcheck):
        # Set the warning message with the result from the first failed check
        failed_check = next(self.failed_checks_with_message, None)

        if failed_check:
            result_message = failed_check.check_status
            # failed ascii check is considered a warning
            if failed_check == self._ascii_check:
                result_icon = "dialog-warning"
            else:
                result_icon = "dialog-error"
            self._passphrase_warning_image.set_from_icon_name(result_icon, Gtk.IconSize.BUTTON)
            self._passphrase_warning_label.set_text(result_message)
            self._passphrase_warning_image.set_visible(True)
            self._passphrase_warning_label.set_visible(True)
        else:
            self._passphrase_warning_image.set_visible(False)
            self._passphrase_warning_label.set_visible(False)

        # The save button should only be sensitive if the match check passes
        if self._confirm_check.check_status == InputCheck.CHECK_OK and \
                (not self.policy.strict or self._strength_check.check_status == InputCheck.CHECK_OK):
            self._save_button.set_sensitive(True)
        else:
            self._save_button.set_sensitive(False)

    def on_save_clicked(self, button):
        self.passphrase = self._passphrase_entry.get_text()

    def on_entry_activated(self, entry):
        if self._save_button.get_sensitive() and \
           entry.get_text() == self._passphrase_entry.get_text():
            self._save_button.emit("clicked")

    def on_passphrase_changed(self, entry):
        self._confirm_check.update_check_status()

    def on_passphrase_confirmation_changed(self, entry):
        self._confirm_check.update_check_status()
