import iutil
from translate import _
from snack import *
from constants_text import *
from constants import *

class BootDiskWindow:
    def __call__(self, screen, dir, disp):
	# we *always* do this for loopback installs
	#
	# XXX
	#
	#if todo.fstab.rootOnLoop():
	    #return INSTALL_NOOP

	buttons = [ _("Yes"), _("No") ]
	text =  _("A custom boot disk provides a way of booting into your "
		  "Linux system without depending on the normal bootloader. "
		  "This is useful if you don't want to install lilo on your "
		  "system, another operating system removes lilo, or lilo "
		  "doesn't work with your hardware configuration. A custom "
		  "boot disk can also be used with the Red Hat rescue image, "
		  "making it much easier to recover from severe system "
		  "failures.\n\n"
		  "Would you like to create a boot disk for your system?")

	if iutil.getArch () == "sparc":
	    floppy = todo.silo.hasUsableFloppy()
	    if floppy == 0:
		todo.bootdisk = 0
		return INSTALL_NOOP
	    text = string.replace (text, "lilo", "silo")
	    if floppy == 1:
		buttons = [ _("No"), _("Yes"), _("Back") ]
		text = string.replace (text, "\n\n",
				       _("\nOn SMCC made Ultra machines floppy booting "
					 "probably does not work\n\n"))

	rc = ButtonChoiceWindow(screen, _("Bootdisk"), text, buttons = buttons,
				help = "bootdiskquery")

	if rc == string.lower (_("No")):
	    disp.skipStep("makebootdisk")
	else:
	    disp.skipStep("makebootdisk", skip = 0)
	

	return INSTALL_OK

class MakeBootDiskWindow:
    def __call__ (self, screen, dir, disp):
	# XXX
	#if todo.fstab.rootOnLoop():
	    #buttons = [ _("OK") ]
	#else:

	# This is a bit gross. This lets the first bootdisk screen skip
	# this one if the user doesn't want to see it.
	if disp.stepInSkipList("makebootdisk"):
	    return INSTALL_NOOP

	buttons = [ _("OK"), _("Skip") ]

	if dir == DISPATCH_FORWARD:
	    rc = ButtonChoiceWindow (screen, _("Bootdisk"),
		     _("If you have the install floppy in your drive, first "
		       "remove it. Then insert a blank floppy in the first "
		       "floppy drive. "
		       "All data on this disk will be erased during creation "
		       "of the boot disk."), buttons, help = "insertbootdisk")
	else:
	    rc = ButtonChoiceWindow (screen, _("Error"),
		    _("An error occured while making the boot disk. "
		      "Please make sure that there is a formatted floppy "
		      "in the first floppy drive."), buttons)

        if rc == string.lower (_("Skip")):
	    disp.skipStep("makebootdisk")
	else:
	    disp.skipStep("makebootdisk", skip = 0)
            
        return INSTALL_OK
