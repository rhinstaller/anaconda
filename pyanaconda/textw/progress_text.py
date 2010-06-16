#
# progress_text.py: text mode install/upgrade progress dialog
#
# Copyright (C) 2001, 2002, 2003, 2004, 2005, 2006, 2007  Red Hat, Inc.
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

from pyanaconda.constants import *
from snack import *
from constants_text import *
from pyanaconda.iutil import strip_markup

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("anaconda")

class InstallProgressWindow:
    def __init__(self, screen):
	self.screen = screen
	self.drawn = False

        self.pct = 0

    def __del__ (self):
	if self.drawn:
            self.screen.popWindow ()

    def _setupScreen(self):
        screen = self.screen

        self.grid = GridForm(self.screen, _("Package Installation"), 1, 6)

        self.width = 65
        self.progress = Scale(self.width, 100)
        self.grid.add (self.progress, 0, 1, (0, 1, 0, 0))

        self.label = Label("")
        self.grid.add(self.label, 0, 2, (0, 1, 0, 0), anchorLeft = 1)

        self.info = Textbox(self.width, 4, "", wrap = 1)
        self.grid.add(self.info, 0, 3, (0, 1, 0, 0))

        self.grid.draw()
        screen.refresh()
        self.drawn = True

    def processEvents(self):
        if not self.drawn:
            return
        self.grid.draw()
        self.screen.refresh()

    def setShowPercentage(self, val):
        pass

    def get_fraction(self):
        return self.pct

    def set_fraction(self, pct):
        if not self.drawn:
            self._setupScreen()

        if pct > 1.0:
            pct = 1.0

        self.progress.set(int(pct * 100))
        self.pct = pct
        self.processEvents()

    def set_label(self, txt):
        if not self.drawn:
            self._setupScreen()
        
        self.info.setText(strip_markup(txt))
        self.processEvents()

    def set_text(self, txt):
        if not self.drawn:
            self._setupScreen()
        
        if len(txt) > self.width:
            txt = txt[:self.width]
        else:
            spaces = (self.width - len(txt)) / 2
            txt = (" " * spaces) + txt
        
        self.label.setText(strip_markup(txt))
        self.processEvents()

class setupForInstall:

    def __call__(self, screen, anaconda):
	if anaconda.dir == DISPATCH_BACK:
	    anaconda.intf.setInstallProgressClass(None)
	    return INSTALL_BACK

        anaconda.intf.setInstallProgressClass(InstallProgressWindow(screen))
	return INSTALL_OK

if __name__ == "__main__":
    screen = SnackScreen()
    ipw = InstallProgressWindow(screen)

    import time
    ipw._setupScreen()
    time.sleep(2)

    ipw.set_label("testing blah\n<b>blahblahb</b>lahbl ahalsdfkj")
    ipw.set_text("blah blah blah")
    ipw.set_fraction(0.25)
    time.sleep(2)

    p = ipw.get_fraction()

    screen.finish()
    print(p)
