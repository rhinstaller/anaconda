#
# keyboard_text: text mode keyboard setup dialogs
#
# Copyright 2001-2002 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import isys
import iutil
from snack import *
from constants_text import *
from flags import flags

from rhpl.translate import _

import logging
log = logging.getLogger("anaconda")

class KeyboardWindow:
    def __call__(self, screen, anaconda):
        if flags.serial or flags.virtpconsole:
	    return INSTALL_NOOP
        keyboards = anaconda.id.keyboard.modelDict.keys()
        keyboards.sort ()

	if anaconda.id.keyboard.beenset:
	    default = anaconda.id.keyboard.get ()
	else:
	    default = anaconda.id.instLanguage.getDefaultKeyboard()

        (button, choice) = \
            ListboxChoiceWindow(screen, _("Keyboard Selection"),
                                _("Which model keyboard is attached to this computer?"), keyboards, 
                                buttons = [TEXT_OK_BUTTON, TEXT_BACK_BUTTON], width = 30, scroll = 1, height = 8,
                                default = default, help = "kybd")
        
        if button == TEXT_BACK_CHECK:
            return INSTALL_BACK

        anaconda.id.keyboard.set (keyboards[choice])
	anaconda.id.keyboard.beenset = 1

        anaconda.id.keyboard.activate()

        # FIXME: eventually, kbd.activate will do this
	try:
	    isys.loadKeymap(keyboards[choice])
	except SystemError, (errno, msg):
	    log.error("Could not install keymap %s: %s" % (keyboards[choice], msg))
        return INSTALL_OK

