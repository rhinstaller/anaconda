#
# bootdisk_text.py: text mode bootdisk creation
#
# Copyright 2000-2002 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import iutil
from rhpl.translate import _
from snack import *
from constants_text import *
from constants import *

class BootDiskWindow:
    def __call__(self, screen, dir, disp, fsset):
	if fsset.rootOnLoop():
            disp.skipStep("makebootdisk", skip=0)
	    return INSTALL_NOOP

	buttons = [ _("Yes"), _("No") ]
	text =  _("A custom boot disk provides a way of booting into your "
		  "Linux system without depending on the normal boot loader. "
		  "This is useful if you don't want to install lilo on your "
		  "system, another operating system removes lilo, or lilo "
		  "doesn't work with your hardware configuration. A custom "
		  "boot disk can also be used with the Red Hat rescue image, "
		  "making it much easier to recover from severe system "
		  "failures.\n\n"
		  "Would you like to create a boot disk for your system?")

        # need to fix if we get sparc back up
##	if iutil.getArch () == "sparc":
##	    floppy = todo.silo.hasUsableFloppy()
## 	    if floppy == 0:
## 		todo.bootdisk = 0
## 		return INSTALL_NOOP
## 	    text = string.replace (text, "lilo", "silo")
## 	    if floppy == 1:
## 		buttons = [ _("No"), _("Yes"), _("Back") ]
## 		text = string.replace (text, "\n\n",
## 				       _("\nOn SMCC made Ultra machines "
##                                          "floppy booting probably does "
##                                          "not work\n\n"))

	rc = ButtonChoiceWindow(screen, _("Boot Disk"), text,
                                buttons=buttons,
				help="bootdiskquery")

	if rc == string.lower (_("No")):
	    disp.skipStep("makebootdisk")
	else:
	    disp.skipStep("makebootdisk", skip=0)
	

	return INSTALL_OK

class MakeBootDiskWindow:
    def __call__ (self, screen, dir, disp, fsset):
	if fsset.rootOnLoop():
            buttons = [ _("OK") ]
	else:
            buttons = [ _("OK"), _("Skip") ]

	# This is a bit gross. This lets the first bootdisk screen skip
	# this one if the user doesn't want to see it.
	if disp.stepInSkipList("makebootdisk"):
	    return INSTALL_NOOP

        text = _("The boot disk allows you to boot "
                 "your %s system from a "
                 "floppy diskette.\n\n"
                 "Please remove any diskettes from the "
                 "floppy drive and insert a blank "
                 "diskette. All data will be ERASED "
                 "during creation of the boot disk.") % (productName,)

        if fsset.rootOnLoop():
            text = text + _("\n\nA boot disk is REQUIRED to boot a "
                            "partitionless install.")

        rc = ButtonChoiceWindow (screen, _("Boot Disk"),
                                 text, buttons, help="insertbootdisk")

        if rc == string.lower (_("Skip")):
	    disp.skipStep("makebootdisk")
	else:
	    disp.skipStep("makebootdisk", skip=0)
            
        return INSTALL_OK
