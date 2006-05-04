#
# upgrade_bootloader_text.py: text bootloader dialog for upgrades
#
# Jeremy Katz <katzj@redhat.com>
#
# Copyright, 2002 Red Hat, Inc.
#
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

from snack import *
from constants_text import *
from rhpl.translate import _
from flags import flags
import string
import iutil
import checkbootloader

class UpgradeBootloaderWindow:

    def __call__(self, screen, anaconda):
        self.dispatch = anaconda.dispatch
        self.bl = anaconda.id.bootloader

        (self.type, self.bootDev) = \
                    checkbootloader.getBootloaderTypeAndBoot(anaconda.rootPath)

        blradio = RadioGroup()

        (update, newbl, nobl) = (0, 0, 0)
        if not self.dispatch.stepInSkipList("bootloader"):
            newbl = 1
        elif self.dispatch.stepInSkipList("instbootloader"):
            nobl = 1
        else:
            if self.type is not None and self.bootDev is not None:
                update = 1
            else:
                nobl = 1
        
        if self.type is not None and self.bootDev is not None:
            t = TextboxReflowed(53,
                                _("The installer has detected the %s boot "
                                  "loader currently installed on %s.")
                                % (self.type, self.bootDev))

            self.update_radio = blradio.add(_("Update boot loader configuration"),
                                            "update", update)
        else:
            t = TextboxReflowed(53,
                  _("The installer is unable to detect the boot loader "
                    "currently in use on your system."))

            self.update_radio = blradio.add(_("Update boot loader configuration"),
                                            "update", update)
            self.update_radio.w.checkboxSetFlags(FLAG_DISABLED, FLAGS_SET)

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
                self.bl.setDevice(self.bootDev)



            screen.popWindow()
            return INSTALL_OK
