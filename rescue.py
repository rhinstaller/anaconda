import upgrade
from snack import *
from text import WaitWindow
from translate import _
import raid
import os

class RescueInterface:

    def waitWindow(self, title, text):
	return WaitWindow(self.screen, title, text)

    def __init__(self, screen):
	self.screen = screen

def runRescue(serial):

    screen = SnackScreen()
    intf = RescueInterface(screen)

    from fstab import NewtFstab

    fstab = NewtFstab(1, serial, 0, 0, None, None, None, 0, [], 0, 0)

    parts = upgrade.findExistingRoots(intf, fstab)

    if not parts:
	root = None
    elif len(parts) == 1:
	root = parts[0]
    else:
	height = min (len (parts), 12)
	if height == 12:
	    scroll = 1
	else:
	    scroll = 0

	partList = []
	for (drive, fs) in parts:
	    partList.append(drive)

	(button, choice) = \
	    ListboxChoiceWindow(screen, _("System to Rescue"),
				_("What partition holds the root partition "
				  "of your installation?"), partList, 
				[ _("OK"), _("Exit") ], width = 30,
				scroll = scroll, height = height,
				help = "multipleroot")

	if button == string.lower (_("Exit")):
	    root = None
	else:
	    root = parts[choice]

    if root:
	try:
	    upgrade.mountRootPartition(root, fstab, '/mnt/sysimage', 
			       allowDirty = 1)
	    ButtonChoiceWindow(screen, _("Rescue"),
		_("Your system has been mounted under /mnt/sysimage.\n\n"
		  "Press <return> to get a shell. The system will reboot "
		  "automatically when you exit from the shell."),
		  [_("OK")] )
	except SystemError, msg:
	    ButtonChoiceWindow(screen, _("Rescue").
		_("An error occured trying to mount some or all of your "
		  "system. Some of it may be mounted under /mnt/sysimage.\n\n"
		  "Press <return> to get a shell. The system will reboot "
		  "automatically when you exit from the shell."),
		  [_("OK")] )
    else:
	ButtonChoiceWindow(screen, _("Rescue Mode"),
			   _("You don't have any Linux partitions. Press "
			     "return to get a shell. The system will reboot "
			     "automatically when you exit from the shell."),
			   [ _("Back") ], width = 50)

    screen.finish()

    for file in [ "services", "protocols", "group" ]:
       os.symlink('/mnt/runtime/etc/' + file, '/etc/' + file)

    print
    print _("Your system is mounted under the /mnt/sysimage directory."
    print

    os.execv("/bin/sh", [ "-/bin/sh" ])
