from snack import *
from constants_text import *
from translate import _
import isys
import iutil
from log import *
from flags import flags

class KeyboardWindow:
    beenRun = 0

    def __call__(self, screen, instLang, kbd):
	if flags.serial:
	    return INSTALL_NOOP
        keyboards = kbd.available ()
        keyboards.sort ()

	if self.beenRun:
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
	self.beenRun = 1

	if flags.reconfig:
	    iutil.execWithRedirect ("/bin/loadkeys",
				    ["/bin/loadkeys", keyboards[choice]],
				    stderr = "/dev/null")

	try:
	    isys.loadKeymap(keyboards[choice])
	except SystemError, (errno, msg):
		log("Could not install keymap %s: %s" % (keyboards[choice], msg))
        return INSTALL_OK

