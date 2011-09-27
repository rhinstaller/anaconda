#
# keyboard_gui.py:  Shim around system-config-keyboard
# Brrrraaaaaiiiinnnns...
#
# Copyright (C) 2006, 2007  Red Hat, Inc.  All rights reserved.
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

from iw_gui import *
from pyanaconda.constants import ROOT_PATH
import sys

sys.path.append("/usr/share/system-config-keyboard")

from keyboard_gui import childWindow as installKeyboardWindow

class KeyboardWindow(InstallWindow, installKeyboardWindow):
    def __init__(self, ics):
        InstallWindow.__init__(self, ics)
        installKeyboardWindow.__init__(self)

        ics.cw.mainxml.get_widget("nextButton").grab_focus()

    def getNext(self):
        installKeyboardWindow.getNext(self)

    def getScreen(self, anaconda):
        default = anaconda.instLanguage.getDefaultKeyboard()
        anaconda.keyboard.set(default)
        vbox = installKeyboardWindow.getScreen(self, default, anaconda.keyboard)
        self.modelView.connect("select-cursor-row", lambda widget, vbox=vbox: self.ics.setGrabNext(1))

        return vbox
