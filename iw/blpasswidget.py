#
# blpasswidget.py - widget for setting of a boot loader password
#
# Copyright (C) 2001, 2002  Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Author(s): Jeremy Katz <katzj@redhat.com>
#

import gtk
import gui
from constants import *

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

class BootloaderPasswordWidget:
    def __init__(self, anaconda, parent):
        self.parent = parent
        self.intf = anaconda.intf
        
        if anaconda.bootloader.getPassword():
            usePass = 1
            self.password = anaconda.bootloader.getPassword()
        else:
            usePass = 0
            self.password = None
        
        vbox = gtk.VBox(False, 6)

        # password widgets + callback
        self.usePassCb = gtk.CheckButton(_("_Use a boot loader password"))
        self.usePassCb.set_tooltip_text(_("A boot loader password prevents users from changing kernel options, increasing security."))
        self.passButton = gtk.Button("No password")
        if usePass:
            self.usePassCb.set_active(True)
            self.passButton.set_sensitive(True)
        else:
            self.usePassCb.set_active(False)
            self.passButton.set_sensitive(False)
        self.usePassCb.connect("toggled", self.passCallback)
        self.passButton.connect("clicked", self.passButtonCallback)
        self.setPassLabel()
            
        box = gtk.HBox(False, 12)
        box.pack_start(self.usePassCb, False)
        box.pack_start(self.passButton, False)
        vbox.pack_start(box, False)

        self.widget = vbox

    def getWidget(self):
        return self.widget

    def getPassword(self):
        # XXX should we handle the only having a crypted password case?
        if self.usePassCb.get_active() and self.password:
            return self.password
        else:
            return None

    # set the label on the button for the bootloader password
    def setPassLabel(self):
        self.passButton.set_label(_("Change _password"))        
        if not self.usePassCb.get_active() or not self.password:
            self.passButton.set_sensitive(False)
        else:
            self.passButton.set_sensitive(True)

    # callback for when the password checkbox is clicked
    def passCallback(self, widget, *args):
        if not widget.get_active():
            self.passButton.set_sensitive(False)
            self.setPassLabel()
        else:
            if self.passwordWindow() == 2:
                widget.set_active(0)
            self.setPassLabel()

    # callback for when the password button is clicked
    def passButtonCallback(self, widget, *args):
        self.passwordWindow()
        self.setPassLabel()

    # get the bootloader password
    def passwordWindow(self, *args):
        dialog = gtk.Dialog(_("Enter Boot Loader Password"), self.parent)
        dialog.add_button('gtk-cancel', 2)
        dialog.add_button('gtk-ok', 1)
        dialog.set_position(gtk.WIN_POS_CENTER)
        gui.addFrame(dialog)
        
        label = gui.WrappingLabel(_("Enter a boot loader password and then confirm it.  (Note that your BIOS keymap may be different than the actual keymap you are used to.)"))
        label.set_alignment(0.0, 0.0)
        dialog.vbox.pack_start(label)

        table = gtk.Table(2, 2)
        table.set_row_spacings(5)
        table.set_col_spacings(5)
        label = gui.MnemonicLabel(_("_Password:"))
        table.attach(label, 0, 1, 2, 3, gtk.FILL, 0, 10)
        pwEntry = gtk.Entry (16)
        pwEntry.set_visibility (False)
        label.set_mnemonic_widget(pwEntry)
        table.attach(pwEntry, 1, 2, 2, 3, gtk.FILL, 0, 10)
        label = gui.MnemonicLabel(_("Con_firm:"))        
        table.attach(label, 0, 1, 3, 4, gtk.FILL, 0, 10) 
        confirmEntry = gtk.Entry (16)
        confirmEntry.set_visibility (False)
        label.set_mnemonic_widget(confirmEntry)
        table.attach(confirmEntry, 1, 2, 3, 4, gtk.FILL, 0, 10)
        dialog.vbox.pack_start(table)

        # set the default
        if self.password:
            pwEntry.set_text(self.password)
            confirmEntry.set_text(self.password)

        dialog.show_all()

        while 1:
            rc = dialog.run()
            if rc in [2, gtk.RESPONSE_DELETE_EVENT]:
                break

            if pwEntry.get_text() != confirmEntry.get_text():
                self.intf.messageWindow(_("Passwords don't match"),
                                        _("Passwords do not match"),
                                        type='warning')
                continue

            thePass = pwEntry.get_text()
            if not thePass:
                continue
            if len(thePass) < 6:
                ret = self.intf.messageWindow(_("Warning"),
                                    _("Your boot loader password is shorter than "
                                      "six characters.  We recommend a longer "
                                      "boot loader password."
                                      "\n\n"
                                      "Would you like to continue with this "
                                      "password?"),
                                             type = "yesno")
                if ret == 0:
                    continue

            self.password = thePass
            break

        dialog.destroy()
        return rc

