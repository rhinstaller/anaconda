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

from gi.repository import Gtk, Gdk

import pwquality

from pyanaconda.ui.gui import GUIObject

from pyanaconda.i18n import _, N_

__all__ = ["PassphraseDialog"]

ERROR_WEAK = N_("You have provided a weak passphrase: %s")
ERROR_NOT_MATCHING = N_("Passphrases do not match.")

class PassphraseDialog(GUIObject):
    builderObjects = ["passphrase_dialog"]
    mainWidgetName = "passphrase_dialog"
    uiFile = "spokes/lib/passphrase.glade"

    def __init__(self, data):
        GUIObject.__init__(self, data)

        self._confirm_entry = self.builder.get_object("confirm_entry")
        self._passphrase_entry = self.builder.get_object("passphrase_entry")

        self._save_button = self.builder.get_object("passphrase_save_button")

        self._strength_label = self.builder.get_object("strength_label")

        # These will be set up later.
        self._strength_bar = None
        self._pwq = None
        self._pwq_error = None
        self.passphrase = ""

    def refresh(self):
        super(PassphraseDialog, self).refresh()

        # disable input methods for the passphrase Entry widgets and make sure
        # the focus change mask is enabled
        self._passphrase_entry.set_property("im-module", "")
        self._passphrase_entry.set_icon_from_stock(Gtk.EntryIconPosition.SECONDARY, "")
        self._passphrase_entry.add_events(Gdk.EventMask.FOCUS_CHANGE_MASK)
        self._confirm_entry.set_property("im-module", "")
        self._confirm_entry.add_events(Gdk.EventMask.FOCUS_CHANGE_MASK)

        self._save_button.set_can_default(True)

        # add the passphrase strength meter
        self._strength_bar = Gtk.LevelBar()
        self._strength_bar.set_mode(Gtk.LevelBarMode.DISCRETE)
        self._strength_bar.set_min_value(0)
        self._strength_bar.set_max_value(4)
        self._strength_bar.add_offset_value("low", 2)
        self._strength_bar.add_offset_value("medium", 3)
        self._strength_bar.add_offset_value("high", 4)
        box = self.builder.get_object("strength_box")
        box.pack_start(self._strength_bar, False, True, 0)
        box.show_all()

        # set up passphrase quality checker
        self._pwq = pwquality.PWQSettings()
        self._pwq.read_config()

        # initialize with the previously set passphrase
        self.passphrase = self.data.autopart.passphrase

        if not self.passphrase:
            self._save_button.set_sensitive(False)

        self._passphrase_entry.set_text(self.passphrase)
        self._confirm_entry.set_text(self.passphrase)

        self._update_passphrase_strength()

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
            self._pwq_error = e[1]

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

    def _set_entry_icon(self, entry, icon, msg):
        entry.set_icon_from_stock(Gtk.EntryIconPosition.SECONDARY, icon)
        entry.set_icon_tooltip_text(Gtk.EntryIconPosition.SECONDARY, msg)

    def on_passphrase_changed(self, entry):
        self._update_passphrase_strength()
        if entry.get_text() and entry.get_text() == self._confirm_entry.get_text():
            self._set_entry_icon(self._confirm_entry, "", "")
            self._save_button.set_sensitive(True)
        else:
            self._save_button.set_sensitive(False)

        if not self._pwq_error:
            self._set_entry_icon(entry, "", "")

    def on_passphrase_editing_done(self, entry, *args):
        if self._pwq_error:
            icon = "gtk-dialog-error"
            msg = _(ERROR_WEAK) % self._pwq_error
            self._set_entry_icon(entry, icon, msg)

    def on_confirm_changed(self, entry):
        if entry.get_text() and entry.get_text() == self._passphrase_entry.get_text():
            self._set_entry_icon(entry, "", "")
            self._save_button.set_sensitive(True)
        else:
            self._save_button.set_sensitive(False)

    def on_confirm_editing_done(self, entry, *args):
        passphrase = self._passphrase_entry.get_text()
        confirm = self._confirm_entry.get_text()
        if passphrase != confirm:
            icon = "gtk-dialog-error"
            msg = ERROR_NOT_MATCHING
            self._set_entry_icon(entry, icon, _(msg))
            self._save_button.set_sensitive(False)
        else:
            self._set_entry_icon(entry, "", "")

    def on_save_clicked(self, button):
        self.passphrase = self._passphrase_entry.get_text()

    def on_entry_activated(self, entry):
        if self._save_button.get_sensitive() and \
           entry.get_text() == self._passphrase_entry.get_text():
            self._save_button.emit("clicked")
