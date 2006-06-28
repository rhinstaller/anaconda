#
# keyboard_gui.py:  Shim around system-config-keyboard
# Brrrraaaaaiiiinnnns...
#
# Copyright 2006 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

from iw_gui import *
import sys

sys.path.append("/usr/share/system-config-keyboard")

from keyboard_gui import KeyboardWindow as installKeyboardWindow

class KeyboardWindow(InstallWindow, installKeyboardWindow):
    def __init__(self, ics):
        InstallWindow.__init__(self, ics)
        installKeyboardWindow.__init__(self, ics)

    def getNext(self):
        installKeyboardWindow.getNext(self)

    def getScreen(self, anaconda):
        return installKeyboardWindow.getScreen(self, anaconda.id.instLanguage.getDefaultKeyboard(),
                                               anaconda.id.keyboard)
