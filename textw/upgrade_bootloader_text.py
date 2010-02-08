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
from flags import flags
import string
from booty import checkbootloader
from storage.devices import devicePathToName

from constants import *
import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("anaconda")

class UpgradeBootloaderWindow:
    def _ideToLibata(self, rootPath):
        try:
            f = open("/proc/modules", "r")
            buf = f.read()
            if buf.find("libata") == -1:
                return False
        except:
            log.debug("error reading /proc/modules")
            pass

        try:
            f = open(rootPath + "/etc/modprobe.conf")
        except:
            log.debug("error reading /etc/modprobe.conf")
            return False

        modlines = f.readlines()
        f.close()

        try:
            f = open("/tmp/scsidisks")
        except:
            log.debug("error reading /tmp/scsidisks")
            return False
        mods = []
        for l in f.readlines():
            (disk, mod) = l.split()
            if mod.strip() not in mods:
                mods.append(mod.strip())
        f.close()

        for l in modlines:
            stripped = l.strip()

            if stripped == "" or stripped[0] == "#":
                continue

            if stripped.find("scsi_hostadapter") != -1:
                mod = stripped.split()[-1]
                if mod in mods:
                    mods.remove(mod)

        if len(mods) > 0:
            return True
        return False

    def __call__(self, screen, anaconda):
        self.screen = screen
        self.dispatch = anaconda.dispatch
        self.bl = anaconda.bootloader

        newToLibata = self._ideToLibata(anaconda.rootPath)
        (self.type, self.bootDev) = \
                    checkbootloader.getBootloaderTypeAndBoot(anaconda.rootPath, storage=anaconda.storage)

        blradio = RadioGroup()

        (update, newbl, nobl) = (0, 0, 0)
        if not self.dispatch.stepInSkipList("bootloader"):
            newbl = 1
        elif self.dispatch.stepInSkipList("instbootloader"):
            nobl = 1
        else:
            if newToLibata or self.type is None or self.bootDev is None:
                newbl = 1
            else:
                update = 1

        if newToLibata or self.type is None or self.bootDev is None:
            if newToLibata:
                t = TextboxReflowed(53,
                    _("Due to system changes, your boot loader "
                      "configuration can not be automatically updated."))
            else:
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
        self.newbl_radio = blradio.add(_("Create new boot loader "
                                         "configuration"),
                                       "newbl", newbl)

        buttons = ButtonBar(screen, [TEXT_OK_BUTTON, TEXT_BACK_BUTTON])

        grid = GridFormHelp(screen, _("Upgrade Boot Loader Configuration"),
                            "bl-upgrade", 1, 5)

        grid.add(t, 0, 0, (0,0,0,1))
        grid.add(self.update_radio, 0, 1, (0,0,0,0))
        grid.add(self.nobl_radio, 0, 2, (0,0,0,0))
        grid.add(self.newbl_radio, 0, 3, (0,0,0,1))
        grid.add(buttons, 0, 4, growx = 1)


        while 1:
            result = grid.run()

            button = buttons.buttonPressed(result)

            if button == TEXT_BACK_CHECK:
                screen.popWindow()
                return INSTALL_BACK        

            if blradio.getSelection() == "nobl":                           
                self.dispatch.skipStep("bootloadersetup", skip = 1)
                self.dispatch.skipStep("bootloader", skip = 1)
                self.dispatch.skipStep("bootloaderadvanced", skip = 1)
                self.dispatch.skipStep("instbootloader", skip = 1)
            elif blradio.getSelection() == "newbl":
                self.dispatch.skipStep("bootloadersetup", skip = 0)
                self.dispatch.skipStep("bootloader", skip = 0)
                self.dispatch.skipStep("bootloaderadvanced", skip = 0)
                self.dispatch.skipStep("instbootloader", skip = 0)
                self.bl.doUpgradeOnly = 0
            else:
                self.dispatch.skipStep("bootloadersetup", skip = 0)
                self.dispatch.skipStep("bootloader", skip = 1)
                self.dispatch.skipStep("bootloaderadvanced", skip = 1)
                self.dispatch.skipStep("instbootloader", skip = 0)
                self.bl.doUpgradeOnly = 1

                if self.type == "GRUB":
                    self.bl.useGrubVal = 1
                else:
                    self.bl.useGrubVal = 0
                self.bl.setDevice(devicePathToName(self.bootDev))



            screen.popWindow()
            return INSTALL_OK
