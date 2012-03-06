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

import snack
from constants_text import INSTALL_OK, INSTALL_BACK, TEXT_BACK_CHECK
from constants_text import TEXT_OK_BUTTON, TEXT_BACK_BUTTON

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("anaconda")

class UpgradeBootloaderWindow:
    def __call__(self, screen, anaconda):
        self.screen = screen

        self.dispatch = anaconda.dispatch
        self.anaconda = anaconda

        (newbl, nobl) = (False, False)
        if self.dispatch.step_enabled("bootloader"):
            newbl = True
        elif self.dispatch.step_disabled("instbootloader"):
            nobl = True
        else:
            newbl = True

        blradio = snack.RadioGroup()
        self.newbl_radio = blradio.add(_("_Create new boot loader configuration"),
                                       "newbl", newbl)
        self.nobl_radio = blradio.add(_("_Skip boot loader updating"),
                                      "nobl", nobl)

        buttons = snack.ButtonBar(screen, [TEXT_OK_BUTTON, TEXT_BACK_BUTTON])

        grid = snack.GridFormHelp(screen, _("Upgrade Boot Loader Configuration"),
                                  "bl-upgrade", 1, 5)

        grid.add(self.newbl_radio, 0, 1, (0,0,0,0))
        grid.add(self.nobl_radio, 0, 2, (0,0,0,0))
        grid.add(buttons, 0, 3, growx = 1)

        while True:
            result = grid.run()

            button = buttons.buttonPressed(result)

            if button == TEXT_BACK_CHECK:
                screen.popWindow()
                return INSTALL_BACK

            if blradio.getSelection() == "nobl":
                self.dispatch.skip_steps("bootloader")
                self.dispatch.skip_steps("instbootloader")
                self.anaconda.bootloader.skip_bootloader = True
            else:
                self.dispatch.request_steps_gently("bootloader")
                self.anaconda.bootloader.skip_bootloader = False

            screen.popWindow()
            return INSTALL_OK

