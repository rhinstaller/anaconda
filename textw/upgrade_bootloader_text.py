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
from translate import _
from flags import flags
import string
import iutil
import checkbootloader

class UpgradeBootloaderWindow:

    def __call__(self, screen, dispatch, bl):
        self.dispatch = dispatch
        self.bl = bl

        (self.type, self.bootDev) = \
                    checkbootloader.getBootloaderTypeAndBoot("/mnt/sysimage")

        blradio = RadioGroup()

        (update, newbl, nobl) = (0, 0, 0)
        if not dispatch.stepInSkipList("bootloader"):
            newbl = 1
        elif dispatch.stepInSkipList("instbootloader"):
            nobl = 1
        else:
            if self.type != None:
                update = 1
            else:
                nobl = 0
        
        if self.type != None:
            t = TextboxReflowed(53,
                  _("Your current boot loader is %s installed on %s.  On an "
                    "upgrade, you can choose to either just have this boot "
                    "loader configuration be updated for the newer kernel "
                    "package being installed, not change your boot loader "
                    "configuration, or write a new boot loader configuration."
                    "\n\n"
                    "What would you like to do?") % (self.type, self.bootDev))

            self.update_radio = blradio.add(_("Update boot loader "
                                              "configuration"),
                                            "update", update)
        else:
            t = TextboxReflowed(53,
                  _("We are unable to determine what boot loader you are "
                    "currently using.  Would you like to not do any boot "
                    "loader configuration or create a new boot loader "
                    "configuration?"))

            self.update_radio = blradio.add(_("Update boot loader "
                                              "configuration"),
                                            "update", update)
            self.update_radio.w.checkboxSetFlags(FLAG_DISABLED, FLAGS_SET)

        self.nobl_radio = blradio.add(_("Skip boot loader updating"),
                                      "nobl", nobl)
        self.newbl_radio = blradio.add(_("Create new boot loader config"),
                                       "newbl", newbl)

        buttons = ButtonBar(screen, [TEXT_OK_BUTTON, TEXT_BACK_BUTTON])

        grid = GridFormHelp(screen, _("Upgrade Boot Loader Configuration"),
                            "upgbootloader", 1, 5)

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
                self.dispatch.skipStep("bootloaderpassword", skip = 1)
                self.dispatch.skipStep("instbootloader", skip = 1)
            if blradio.getSelection() == "newbl":
                self.dispatch.skipStep("bootloadersetup", skip = 0)
                self.dispatch.skipStep("bootloader", skip = 0)
                self.dispatch.skipStep("bootloaderpassword", skip = 0)
                self.dispatch.skipStep("instbootloader", skip = 0)
                self.bl.doUpgradeOnly = 0
            else:
                self.dispatch.skipStep("bootloadersetup", skip = 0)
                self.dispatch.skipStep("bootloader", skip = 1)
                self.dispatch.skipStep("bootloaderpassword", skip = 1)
                self.bl.doUpgradeOnly = 1

                if self.type == "GRUB":
                    self.bl.useGrubVal = 1
                else:
                    self.bl.useGrubVal = 0
                self.bl.setDevice(self.bootDev)



            screen.popWindow()
            return INSTALL_OK
