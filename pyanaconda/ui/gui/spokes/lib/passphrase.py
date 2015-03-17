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

from gi.repository import Gtk

import pwquality

from pyanaconda.ui.helpers import InputCheck
from pyanaconda.ui.gui import GUIObject
from pyanaconda.ui.gui.helpers import GUIInputCheckHandler
from pyanaconda.constants import PW_ASCII_CHARS
from pyanaconda.i18n import _, N_
from pyanaconda.ui.gui.utils import really_hide, really_show

__all__ = ["PassphraseDialog"]

ERROR_WEAK = N_("You have provided a weak passphrase: %s")
ERROR_NOT_MATCHING = N_("Passphrases do not match.")

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

        # These will be set up later.
        self._pwq = None
        self._pwq_error = None
        self.passphrase = ""

        self._passphrase_match_check = self.add_check(self._passphrase_entry, self._checkMatch)
        self._confirm_match_check = self.add_check(self._confirm_entry, self._checkMatch)
        self._strength_check = self.add_check(self._passphrase_entry, self._checkStrength)
        self._ascii_check = self.add_check(self._passphrase_entry, self._checkASCII)

    def refresh(self):
        super(PassphraseDialog, self).refresh()

        # disable input methods for the passphrase Entry widgets
        self._passphrase_entry.set_property("im-module", "")
        self._confirm_entry.set_property("im-module", "")

        # set up passphrase quality checker
        self._pwq = pwquality.PWQSettings()
        self._pwq.read_config()
        self._pwq.minlen = self.policy.minlen

        # initialize with the previously set passphrase
        self.passphrase = self.data.autopart.passphrase

        if not self.passphrase:
            self._save_button.set_sensitive(False)

        self._passphrase_entry.set_text(self.passphrase)
        self._confirm_entry.set_text(self.passphrase)

        self._update_passphrase_strength()

        # Update the check states and force a status update
        self._passphrase_match_check.update_check_status()
        self._strength_check.update_check_status()
        self._ascii_check.update_check_status()
        self.set_status(None)

    def run(self):
        self.refresh()
        self.window.show_all()
        rc = self.window.run()
        self.window.destroy()
        return rc

    def _update_passphrase_strength(self):
        passphrase = self._passphrase_entry.get_text()
        strength = 0
        self._pwq_error = ""
        try:
            strength = self._pwq.check(passphrase, None, None)
        except pwquality.PWQError as e:
            self._pwq_error = e.args[1]

        if strength < 50:
            val = 1
            text = _("Weak")
        elif strength < 75:
            val = 2
            text = _("Fair")
        elif strength < 90:
            val = 3
            text = _("Good")
        else:
            val = 4
            text = _("Strong")

        self._strength_bar.set_value(val)
        self._strength_label.set_text(text)

    def set_status(self, inputcheck):
        # Set the warning message with the result from the first failed check
        failed_check = next(self.failed_checks_with_message, None)

        if failed_check:
            result_icon, result_message = failed_check.check_status
            self._passphrase_warning_image.set_from_icon_name(result_icon, Gtk.IconSize.BUTTON)
            self._passphrase_warning_label.set_text(result_message)
            really_show(self._passphrase_warning_image)
            really_show(self._passphrase_warning_label)
        else:
            really_hide(self._passphrase_warning_image)
            really_hide(self._passphrase_warning_label)

        # The save button should only be sensitive if the match check passes
        if self._passphrase_match_check.check_status == InputCheck.CHECK_OK and \
                self._confirm_match_check.check_status == InputCheck.CHECK_OK and \
                (not self.policy.strict or self._strength_check.check_status == InputCheck.CHECK_OK):
            self._save_button.set_sensitive(True)
        else:
            self._save_button.set_sensitive(False)

    def _checkASCII(self, inputcheck):
        passphrase = self.get_input(inputcheck.input_obj)

        if passphrase and any(char not in PW_ASCII_CHARS for char in passphrase):
            return ("dialog-warning", _("Passphrase contains non-ASCII characters"))
        else:
            return InputCheck.CHECK_OK

    def _checkStrength(self, inputcheck):
        if self._pwq_error:
            return ("dialog-error", _(ERROR_WEAK) % self._pwq_error)
        else:
            return InputCheck.CHECK_OK

    def _checkMatch(self, inputcheck):
        passphrase = self._passphrase_entry.get_text()
        confirm = self._confirm_entry.get_text()
        if passphrase != confirm:
            result = ("dialog-error", _(ERROR_NOT_MATCHING))
        else:
            result = InputCheck.CHECK_OK

        # If the check succeeded, reset the status of the other check object
        # Disable the current check to prevent a cycle
        if result == InputCheck.CHECK_OK:
            inputcheck.enabled = False
            if inputcheck == self._passphrase_match_check:
                self._confirm_match_check.update_check_status()
            else:
                self._passphrase_match_check.update_check_status()
            inputcheck.enabled = True

        return result

    def on_passphrase_changed(self, entry):
        self._update_passphrase_strength()

    def on_save_clicked(self, button):
        self.passphrase = self._passphrase_entry.get_text()

    def on_entry_activated(self, entry):
        if self._save_button.get_sensitive() and \
           entry.get_text() == self._passphrase_entry.get_text():
            self._save_button.emit("clicked")
