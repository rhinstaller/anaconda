#
# keyboard_text: text mode keyboard setup dialogs
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

import isys
from snack import *
from constants_text import *
from flags import flags

from constants import *
import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("anaconda")

class KeyboardWindow:
    def __call__(self, screen, anaconda):
        if flags.serial or flags.virtpconsole:
	    return INSTALL_NOOP
        keyboards = anaconda.keyboard.modelDict.keys()
        keyboards.sort ()

	if anaconda.keyboard.beenset:
	    default = anaconda.keyboard.get ()
	else:
	    default = anaconda.instLanguage.getDefaultKeyboard(anaconda.rootPath)

        if default not in keyboards:
            default = 'us'

        (button, choice) = \
            ListboxChoiceWindow(screen, _("Keyboard Selection"),
                                _("Which model keyboard is attached to this computer?"), keyboards, 
                                buttons = [TEXT_OK_BUTTON, TEXT_BACK_BUTTON], width = 30, scroll = 1, height = 8,
                                default = default, help = "kybd")
        
        if button == TEXT_BACK_CHECK:
            return INSTALL_BACK

        anaconda.keyboard.set (keyboards[choice])
        anaconda.keyboard.beenset = 1

        anaconda.keyboard.activate()

        # FIXME: eventually, kbd.activate will do this
	try:
	    isys.loadKeymap(keyboards[choice])
	except SystemError, (errno, msg):
	    log.error("Could not install keymap %s: %s" % (keyboards[choice], msg))
        return INSTALL_OK

