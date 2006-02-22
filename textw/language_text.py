#
# language_text.py: text mode language selection dialog
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

import os
import isys
import iutil
import time
from snack import *
from constants_text import *
from flags import flags

from rhpl.translate import _

import logging
log = logging.getLogger("anaconda")

class LanguageWindow:
    def __call__(self, screen, textInterface, instLanguage):
        languages = instLanguage.available ()

        current = instLanguage.getCurrent()

        height = min((8, len(languages)))
	buttons = [TEXT_OK_BUTTON, TEXT_BACK_BUTTON]

        translated = []
        for lang in languages:
            translated.append ((_(lang), instLanguage.getNickByName(lang)))
        (button, choice) = \
            ListboxChoiceWindow(screen, _("Language Selection"),
			_("What language would you like to use during the "
			  "installation process?"), translated, 
			buttons, width = 30, default = _(current), scroll = 1,
                                height = height, help = "lang")

        if button == TEXT_BACK_CHECK:
            return INSTALL_BACK

        if ((instLanguage.getFontFile(choice) == "None")):
            ButtonChoiceWindow(screen, "Language Unavailable",
                               "%s display is unavailable in text mode.  The "
                               "installation will continue in English." % (choice,),
                               buttons=[TEXT_OK_BUTTON])
            instLanguage.setRuntimeDefaults(choice)
            return INSTALL_OK

        if (flags.setupFilesystems and
            instLanguage.getFontFile(choice) == "none"
            and textInterface.isRealConsole()):
            ButtonChoiceWindow(screen, "Language Unavailable",
                               "%s display is unavailable in text mode.  "
                               "The installation will continue in "
                               "English." % (choice,),
                               buttons=[TEXT_OK_BUTTON])
            instLanguage.setRuntimeDefaults(choice)
            return INSTALL_OK

	instLanguage.setRuntimeLanguage(choice)
	instLanguage.setDefault(choice)
                
	textInterface.drawFrame()
	    
        return INSTALL_OK
