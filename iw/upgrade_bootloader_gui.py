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
    htmlTag = "bl-upgrade"

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


        self.update_radio = GtkRadioButton(None, _("Update boot loader configuration"))
        updatestr = _("This will update your current boot loader.")

        if self.type != None:
            current = _("The installer has detected the %s boot loader "
                        "currently installed on %s.") % (self.type,
                                                         self.bootDev)
            self.update_label = GtkLabel(N_("%s  %s") % (updatestr,
                                         _("This is the recommended option.")))
            self.update_radio.set_active(FALSE)
            update = 1
        else:
            current = _("The installer is unable to detect the boot loader "
                        "currently in use on your system.")
            self.update_label = GtkLabel(N_("%s") % (updatestr,))
            self.update_radio.set_sensitive(FALSE)
            self.update_label.set_sensitive(FALSE)
            update = 0
            
    
        self.newbl_radio = GtkRadioButton(self.update_radio,
                                          _("Create new boot loader "
                                            "configuration"))
        self.newbl_label = GtkLabel(_("This will let you create a "
                                      "new boot loader configuration.  If "
                                      "you wish to switch boot loaders, you "
                                      "should choose this."))
                                      
        self.newbl_radio.set_active(FALSE)
        self.nobl_radio = GtkRadioButton(self.update_radio,
                                         _("Skip boot loader updating"))
        self.nobl_label = GtkLabel(_("This will make no changes to boot "
                                     "loader configuration.  If you are "
                                     "using a third party boot loader, you "
                                     "should choose this."))
        self.nobl_radio.set_active(FALSE)

        for label in [self.update_label, self.nobl_label, self.newbl_label]:
            label.set_alignment(0.8, 0)
            label.set_usize(275, -1)
            label.set_line_wrap(TRUE)


        str = _("What would you like to do?")
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


        box = GtkVBox(FALSE, 5)

        label = GtkLabel(current)
        label.set_line_wrap(TRUE)
        label.set_alignment(0.5, 0.0)
        label.set_usize(300, -1)
        label2 = GtkLabel(str)
        label2.set_line_wrap(TRUE)
        label2.set_alignment(0.5, 0.0)
        label2.set_usize(300, -1)

        box.pack_start(label, FALSE)
        box.pack_start(label2, FALSE, padding = 10)

        box.pack_start(self.update_radio, FALSE)
        box.pack_start(self.update_label, FALSE)
        box.pack_start(self.nobl_radio, FALSE)
        box.pack_start(self.nobl_label, FALSE)
        box.pack_start(self.newbl_radio, FALSE)
        box.pack_start(self.newbl_label, FALSE)        

        a = GtkAlignment(0.2, 0.1)
        a.add(box)

        return a
