import iutil
from translate import _
from snack import *
from textw.constants import *

class BootDiskWindow:
    def __call__(self, screen, todo):
	# we *always* do this for loopback installs
	if todo.fstab.rootOnLoop():
	    return INSTALL_NOOP

	buttons = [ _("Yes"), _("No"), _("Back") ]
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

	rc = ButtonChoiceWindow(screen, _("Bootdisk"), text, buttons = buttons)

	if rc == string.lower (_("Yes")):
	    todo.bootdisk = 1
	
	if rc == string.lower (_("No")):
	    todo.bootdisk = 0

	if rc == string.lower (_("Back")):
	    return INSTALL_BACK
	return INSTALL_OK

class MakeBootDiskWindow:
    def __call__ (self, screen, todo):
        if not todo.needBootdisk():
            return INSTALL_NOOP

        rc = ButtonChoiceWindow (screen, _("Bootdisk"),
		     _("Insert a blank floppy in the first floppy drive. "
		       "All data on this disk will be erased during creation "
		       "of the boot disk."),
		     [ _("OK"), _("Skip") ])                
        if rc == string.lower (_("Skip")):
            return INSTALL_OK
            
        while 1:
            try:
                todo.makeBootdisk ()
            except:
                rc = ButtonChoiceWindow (screen, _("Error"),
			_("An error occured while making the boot disk. "
			  "Please make sure that there is a formatted floppy "
			  "in the first floppy drive."),
			  [ _("OK"), _("Skip")] )
                if rc == string.lower (_("Skip")):
                    break
                continue
            else:
                break
            
        return INSTALL_OK

