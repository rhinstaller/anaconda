#
# upgrade_bootloader_text.py: text bootloader dialog for upgrades
#
# Copyright (C) 2002  Red Hat, Inc.  All rights reserved.
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
# Author(s): Jeremy Katz <katzj@redhat.com>
#

from snack import *
from constants_text import *
from pyanaconda.flags import flags
from pyanaconda.constants import *

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("anaconda")

class UpgradeBootloaderWindow:
    def __call__(self, screen, anaconda):
        self.screen = screen

        self.type = None
        self.bootDev = None

        blradio = RadioGroup()

        update = False
        nobl = False
        if anaconda.dispatch.stepInSkipList("instbootloader"):
            nobl = True
        elif self.type and self.bootDev:
            update = True

        if (not anaconda.bootloader.can_update) or \
           (self.type is None or self.bootDev is None):
            t = TextboxReflowed(53,
              _("The installer is unable to detect the boot loader "
                "currently in use on your system."))

            self.update_radio = blradio.add(_("Update boot loader configuration"),
                                            "update", update)
            self.update_radio.w.checkboxSetFlags(FLAG_DISABLED, FLAGS_SET)
        else:
            t = TextboxReflowed(53,
                                _("The installer has detected the %(type)s "
                                  "boot loader currently installed on "
                                  "%(bootDev)s.")
                                % {'type': self.type, 'bootDev': self.bootDev})

            self.update_radio = blradio.add(_("Update boot loader configuration"),
                                            "update", update)

        self.nobl_radio = blradio.add(_("Skip boot loader updating"),
                                      "nobl", nobl)

        buttons = ButtonBar(screen, [TEXT_OK_BUTTON, TEXT_BACK_BUTTON])

        grid = GridFormHelp(screen, _("Upgrade Boot Loader Configuration"),
                            "bl-upgrade", 1, 5)

        grid.add(t, 0, 0, (0,0,0,1))
        grid.add(self.update_radio, 0, 1, (0,0,0,0))
        grid.add(self.nobl_radio, 0, 2, (0,0,0,0))
        grid.add(buttons, 0, 3, growx = 1)

        while True:
            result = grid.run()

            button = buttons.buttonPressed(result)

            if button == TEXT_BACK_CHECK:
                screen.popWindow()
                return INSTALL_BACK        

            if blradio.getSelection() == "nobl":                           
                self.dispatch.skipStep("bootloader", skip = 1)
                self.dispatch.skipStep("instbootloader", skip = 1)
               anaconda.bootloader.update_only = False
            else:
                self.dispatch.skipStep("bootloader", skip = 1)
                self.dispatch.skipStep("instbootloader", skip = 0)
                anaconda.bootloader.update_only = anaconda.bootloader.can_update

            screen.popWindow()
            return INSTALL_OK
