#
# keyboard_text: text mode keyboard setup dialogs
#
# Copyright 2001 Red Hat, Inc.
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
from translate import _
from log import *
from flags import flags

class KeyboardWindow:
    def __call__(self, screen, instLang, kbd, xconfig):
	if flags.serial:
	    return INSTALL_NOOP
        keyboards = kbd.available ()
        keyboards.sort ()

	if kbd.beenset:
	    default = kbd.get ()
	else:
	    default = instLang.getDefaultKeyboard()

        (button, choice) = \
            ListboxChoiceWindow(screen, _("Keyboard Selection"),
                                _("Which model keyboard is attached to this computer?"), keyboards, 
                                buttons = [TEXT_OK_BUTTON, TEXT_BACK_BUTTON], width = 30, scroll = 1, height = 8,
                                default = default, help = "kybd")
        
        if button == TEXT_BACK_CHECK:
            return INSTALL_BACK

        kbd.set (keyboards[choice])
	kbd.beenset = 1

	if (xconfig != (None, None)):
            apply(xconfig.setKeyboard, kbd.getXKB())

	if flags.reconfig:
	    iutil.execWithRedirect ("/bin/loadkeys",
				    ["/bin/loadkeys", keyboards[choice]],
				    stderr = "/dev/null")

	try:
	    isys.loadKeymap(keyboards[choice])
	except SystemError, (errno, msg):
		log("Could not install keymap %s: %s" % (keyboards[choice], msg))
        return INSTALL_OK

