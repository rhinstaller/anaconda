#
# upgrade_bootloader_gui.py: gui bootloader dialog for upgrades
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

# must replace with explcit form so update disks will work
from iw_gui import *

from gtk import *
from gnome.ui import *
from translate import _, N_
import gdkpixbuf
import iutil
import gui
import checkbootloader

class UpgradeBootloaderWindow (InstallWindow):
    windowTitle = N_("Upgrade Boot Loader Configuration")
    htmlTag = "bootloader-upgrade"

    def getPrev(self):
        pass

    def getNext(self):
        if self.nobl_radio.get_active():
            self.dispatch.skipStep("bootloadersetup", skip = 1)
            self.dispatch.skipStep("bootloader", skip = 1)
            self.dispatch.skipStep("bootloaderpassword", skip = 1)
            self.dispatch.skipStep("instbootloader", skip = 1)
        elif self.newbl_radio.get_active():
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


    def getScreen(self, dispatch, bl):
        self.dispatch = dispatch
        self.bl = bl
        self.intf = dispatch.intf

        (self.type, self.bootDev) = \
                    checkbootloader.getBootloaderTypeAndBoot("/mnt/sysimage")

        if self.type != None:
            str = _("Your current boot loader is %s installed on %s.  On an "
                    "upgrade, you can choose to either just have this boot "
                    "loader configuration be updated for the newer kernel "
                    "package being installed, not change your boot loader "
                    "configuration, or write a new boot loader configuration."
                    "\n\n"
                    "What would you like to do?") % (self.type, self.bootDev)

            self.update_radio = GtkRadioButton(None, _("Update boot loader "
                                                       "configuration"))
            self.update_radio.set_active(FALSE)
            update = 1
        else:
            str = _("We are unable to determine what boot loader you are "
                    "currently using.  Would you like to not do any boot "
                    "loader configuration or create a new boot loader "
                    "configuration?")

            self.update_radio = GtkRadioButton(None, _("Update boot loader "
                                                       "configuration"))
            self.update_radio.set_sensitive(FALSE)
            update = 0
            
    
        self.nobl_radio = GtkRadioButton(self.update_radio,
                                         _("Skip boot loader updating"))
        self.nobl_radio.set_active(FALSE)
        self.newbl_radio = GtkRadioButton(self.update_radio,
                                          _("Create new boot loader config"))
        self.newbl_radio.set_active(FALSE)


        # if they have one, the default is to update, otherwise the
        # default is to not touch anything
        if update == 1:
            default = self.update_radio
        else:
            default = self.nobl_radio
        

        if not dispatch.stepInSkipList("bootloader"):
            self.newbl_radio.set_active(TRUE)
        elif dispatch.stepInSkipList("instbootloader"):
            self.nobl_radio.set_active(TRUE)
        else:
            default.set_active(TRUE)


        box = GtkVBox(FALSE, 0)

        label = GtkLabel(str)
        label.set_line_wrap(TRUE)
        label.set_alignment(0.0, 0.0)
        label.set_usize(400, -1)

        box.pack_start(label, FALSE)

        if self.update_radio:
            box.pack_start(self.update_radio, FALSE)
        box.pack_start(self.nobl_radio, FALSE)
        box.pack_start(self.newbl_radio, FALSE)

        return box
