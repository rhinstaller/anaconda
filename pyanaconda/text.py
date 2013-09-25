#
# Copyright (C) 1999, 2000, 2001, 2002, 2003, 2004, 2005, 2006  Red Hat, Inc.
# All rights reserved.
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
# Author(s): Erik Troan <ewt@redhat.com>
#            Matt Wilson <msw@redhat.com>
#

from snack import ButtonBar, ButtonChoiceWindow, Entry, GridForm, Scale, TextboxReflowed
from pyanaconda.constants_text import TEXT_OK_BUTTON, TEXT_CANCEL_BUTTON, TEXT_OK_CHECK
from pyanaconda.i18n import _

class WaitWindow:
    def pop(self):
        self.screen.popWindow()
        self.screen.refresh()

    def refresh(self):
        pass

    def __init__(self, screen, title, text):
        self.screen = screen
        width = 40
        if (len(text) < width):
            width = len(text)

        t = TextboxReflowed(width, text)

        g = GridForm(self.screen, title, 1, 1)
        g.add(t, 0, 0)
        g.draw()
        self.screen.refresh()

class OkCancelWindow:
    def getrc(self):
        return self.rc

    def __init__(self, screen, title, text):
        rc = ButtonChoiceWindow(screen, title, text, buttons=[TEXT_OK_BUTTON, _("Cancel")])
        if rc == _("Cancel").lower():
            self.rc = 1
        else:
            self.rc = 0

class ProgressWindow:
    def pop(self):
        self.screen.popWindow()
        self.screen.refresh()
        del self.scale
        self.scale = None

    def pulse(self):
        pass

    def set(self, amount):
        self.scale.set(int(float(amount) * self.multiplier))
        self.screen.refresh()

    def refresh(self):
        pass

    def __init__(self, screen, title, text, total, updpct = 0.05, pulse = False):
        self.multiplier = 1
        if total == 1.0:
            self.multiplier = 100
        self.screen = screen
        width = 55
        if (len(text) > width):
            width = len(text)

        t = TextboxReflowed(width, text)

        g = GridForm(self.screen, title, 1, 2)
        g.add(t, 0, 0, (0, 0, 0, 1), anchorLeft=1)

        self.scale = Scale(int(width), int(float(total) * self.multiplier))
        if not pulse:
            g.add(self.scale, 0, 1)

        g.draw()
        self.screen.refresh()

class PassphraseEntryWindow:
    def __init__(self, screen, device):
        self.screen = screen
        self.txt = _("Device %s is encrypted. In order to "
                     "access the device's contents during "
                     "installation you must enter the device's "
                     "passphrase below.") % (device,)
        self.rc = None

    def run(self):
        toplevel = GridForm(self.screen, _("Passphrase"), 1, 3)

        txt = TextboxReflowed(65, self.txt)
        toplevel.add(txt, 0, 0)

        passphraseentry = Entry(60, password = 1)
        toplevel.add(passphraseentry, 0, 1, (0,0,0,1))

        buttons = ButtonBar(self.screen, [TEXT_OK_BUTTON, TEXT_CANCEL_BUTTON])
        toplevel.add(buttons, 0, 2, growx=1)

        rc = toplevel.run()
        res = buttons.buttonPressed(rc)

        passphrase = None
        if res == TEXT_OK_CHECK or rc == "F12":
            passphrase = passphraseentry.value().strip()

        self.rc = passphrase
        return self.rc

    def pop(self):
        self.screen.popWindow()
