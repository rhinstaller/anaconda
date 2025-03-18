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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#

import gi
gi.require_version("Gtk", "3.0")

from gi.repository import Gtk

from pyanaconda.ui.gui import GUIObject
from pyanaconda.ui.gui.utils import really_hide, really_show, set_password_visibility
from pyanaconda import input_checking
from pyanaconda.core import constants
from pyanaconda.core.constants import PASSWORD_POLICY_LUKS

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

__all__ = ["PassphraseDialog"]


class PassphraseDialog(GUIObject):
    builderObjects = ["passphrase_dialog"]
    mainWidgetName = "passphrase_dialog"
    uiFile = "spokes/lib/passphrase.glade"

    def __init__(self, data, default_passphrase=""):
        super().__init__(data)

        self._passphrase_entry = self.builder.get_object("passphrase_entry")
        self._confirm_entry = self.builder.get_object("confirm_pw_entry")

        self._save_button = self.builder.get_object("passphrase_save_button")

        self._strength_bar = self.builder.get_object("strength_bar")
        self._strength_label = self.builder.get_object("strength_label")

        self._passphrase_warning_image = self.builder.get_object("passphrase_warning_image")
        self._passphrase_warning_label = self.builder.get_object("passphrase_warning_label")

        # Set the offset values for the strength bar colors
        self._strength_bar.add_offset_value("low", 2)
        self._strength_bar.add_offset_value("medium", 3)
        self._strength_bar.add_offset_value("high", 4)

        # Setup the password checker for passphrase checking
        self._checker = input_checking.PasswordChecker(
            initial_password_content=self._passphrase_entry.get_text(),
            initial_password_confirmation_content=self._confirm_entry.get_text(),
            policy_name=PASSWORD_POLICY_LUKS
        )

        # configure the checker for passphrase checking
        self._checker.secret_type = constants.SecretType.PASSPHRASE
        # connect UI updates to check results
        self._checker.checks_done.connect(self._set_status)

        self.passphrase = default_passphrase
        self._passphrase_good_enough = False

        # check that the content of the passphrase field & the conformation field are the same
        self._confirm_check = input_checking.PasswordConfirmationCheck()
        # check passphrase validity, quality and strength
        self._validity_check = input_checking.PasswordValidityCheck()
        # connect UI updates to validity check results
        self._validity_check.result.password_score_changed.connect(self._set_password_strength)
        self._validity_check.result.status_text_changed.connect(self._set_password_status_text)
        # check if the passphrase satisfies the FIPS requirements
        self._fips_check = input_checking.PasswordFIPSCheck()
        # check if the passphrase contains non-ascii characters
        self._ascii_check = input_checking.PasswordASCIICheck()
        # check if the passphrase is empty
        self._empty_check = input_checking.PasswordEmptyCheck()

        # register the individual checks with the checker in proper order
        # 1) are both entered passphrases the same ?
        # 2) is the passphrase valid according to the current password checking policy ?
        # 3) is the passphrase free of non-ASCII characters ?
        self._checker.add_check(self._confirm_check)
        self._checker.add_check(self._validity_check)
        self._checker.add_check(self._fips_check)
        self._checker.add_check(self._ascii_check)
        self._checker.add_check(self._empty_check)

        # set the visibility of the password entries
        # - without this the password visibility toggle icon will
        #   not be shown
        set_password_visibility(self._passphrase_entry, False)
        set_password_visibility(self._confirm_entry, False)

    def refresh(self):
        super().refresh()

        # disable input methods for the passphrase Entry widgets
        self._passphrase_entry.set_property("im-module", "")
        self._confirm_entry.set_property("im-module", "")

        if not self.passphrase:
            self._save_button.set_sensitive(False)

        self._passphrase_entry.set_text(self.passphrase)
        self._confirm_entry.set_text(self.passphrase)

        # run the checks
        self._checker.run_checks()

    def run(self):
        self.refresh()
        self.window.show_all()

        while True:
            rc = self.window.run()
            if rc == 1:
                # Force an update of all the checks and then see if it was successful,
                # just in case.
                self._checker.run_checks()
                if self._passphrase_good_enough:
                    # Input ok, save the passphrase
                    self.passphrase = self._passphrase_entry.get_text()
                    break
                else:
                    # Input not ok, try again
                    continue
            else:
                # Cancel, destroy the window
                break

        self.window.destroy()
        return rc

    def _set_status(self, error_message):
        """Set UI element states according to passphrase check results.

        NOTE: This method is called every time the checker finishes running all checks.
        """
        success = not error_message
        if success:
            really_hide(self._passphrase_warning_image)
            really_hide(self._passphrase_warning_label)
        else:
            if not self._ascii_check.result.success:
                # ASCII check runs last, so if just it has failed the result is only a warning
                result_icon = "dialog-warning"
            else:
                # something else failed and that's a critical error
                result_icon = "dialog-error"
            self._passphrase_warning_image.set_from_icon_name(result_icon, Gtk.IconSize.BUTTON)
            self._passphrase_warning_label.set_text(error_message)
            really_show(self._passphrase_warning_image)
            really_show(self._passphrase_warning_label)

        # The save button should only be sensitive if both passphrases match
        # and are valid enough for current policy
        self._passphrase_good_enough = False
        if self._checker.success:
            self._passphrase_good_enough = True
        elif len(self._checker.failed_checks) == 1 and self._validity_check in self._checker._failed_checks:
            # only the password validity check failed
            if self._checker.policy.is_strict:
                # this is not fine for the strict password policy
                self._passphrase_good_enough = False
            else:
                # but is totally fine under the non-strict policy
                self._passphrase_good_enough = True
        elif len(self._checker.failed_checks) == 1 and self._ascii_check in self._checker._failed_checks:
            # enable the save button if only the ascii check has failed
            self._passphrase_good_enough = True

        # set the save button sensitivity accordingly
        self._save_button.set_sensitive(self._passphrase_good_enough)

    def _set_password_strength(self, strength):
        self._strength_bar.set_value(strength)

    def _set_password_status_text(self, status_text):
        self._strength_label.set_text(status_text)

    def on_passphrase_changed(self, entry):
        self._checker.password.content = entry.get_text()

    def on_confirm_changed(self, entry):
        self._checker.password_confirmation.content = entry.get_text()

    def on_entry_activated(self, entry):
        if self._save_button.get_sensitive() and \
           entry.get_text() == self._passphrase_entry.get_text():
            self._save_button.emit("clicked")

    def on_password_icon_clicked(self, entry, icon_pos, event):
        """Called by Gtk callback when the icon of a password entry is clicked."""
        set_password_visibility(entry, not entry.get_visibility())
