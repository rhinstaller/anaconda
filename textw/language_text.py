#
# language_text.py: text mode language selection dialog
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

from snack import *
from constants_text import *

from constants import *
import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("anaconda")

class LanguageWindow:
    def __call__(self, screen, anaconda):
        languages = anaconda.instLanguage.available ()
        languages.sort()

        current = anaconda.instLanguage.instLang

        height = min((8, len(languages)))
	buttons = [TEXT_OK_BUTTON, TEXT_BACK_BUTTON]

        translated = []
        for lang in languages:
            translated.append ((_(lang), anaconda.instLanguage.getLangByName(lang)))
        (button, choice) = \
            ListboxChoiceWindow(screen, _("Language Selection"),
			_("What language would you like to use during the "
			  "installation process?"), translated, 
			buttons, width = 30, default = _(current), scroll = 1,
                                height = height, help = "lang")

        if button == TEXT_BACK_CHECK:
            return INSTALL_BACK

        if anaconda.instLanguage.getFontFile(choice) == "none":
            ButtonChoiceWindow(screen, "Language Unavailable",
                               "%s display is unavailable in text mode.  The "
                               "installation will continue in English." % (choice,),
                               buttons=[TEXT_OK_BUTTON])
            anaconda.instLanguage.instLang = choice
            anaconda.instLanguage.systemLang = choice
            anaconda.timezone.setTimezoneInfo(anaconda.instLanguage.getDefaultTimeZone(anaconda.rootPath))
            return INSTALL_OK

        anaconda.instLanguage.instLang = choice
        anaconda.instLanguage.systemLang = choice
        anaconda.timezone.setTimezoneInfo(anaconda.instLanguage.getDefaultTimeZone(anaconda.rootPath))

	anaconda.intf.drawFrame()

        return INSTALL_OK
