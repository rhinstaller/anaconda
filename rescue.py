#
# rescue.py - anaconda rescue mode setup
#
# Mike Fulbright <msf@redhat.com>
#
# Copyright 2001 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import upgrade
from snack import *
from text import WaitWindow, OkCancelWindow
from translate import _
import sys
import os
from log import log
import isys
import fsset

class RescueInterface:

    def waitWindow(self, title, text):
	return WaitWindow(self.screen, title, text)

    def messageWindow(self, title, text, type = "ok"):
	if type == "ok":
	    ButtonChoiceWindow(self.screen, _(title), _(text),
			       buttons = [ _("OK") ])
	else:
	    return OkCancelWindow(self.screen, _(title), _(text))

    def __init__(self, screen):
	self.screen = screen

def runRescue(instPath, mountroot, id):

    for file in [ "services", "protocols", "group" ]:
       os.symlink('/mnt/runtime/etc/' + file, '/etc/' + file)

    if (not mountroot):
        print
        print _("When finished please exit from the shell and your "
                "system will reboot.")
        print
	os.execv("/bin/sh", [ "-/bin/sh" ])

    # lets create some devices
    for drive in isys.hardDriveDict().keys():
	isys.makeDevInode(drive, "/dev/" + drive)
	
	for i in range(16):
	    if drive [:3] == "rd/" or drive [:4] == "ida/" or drive [:6] == "cciss/":
		dev = drive + 'p' + str (i + 1)
	    else:
		dev = drive + str (i + 1)

	    isys.makeDevInode(dev, "/dev/" + dev)

    screen = SnackScreen()
    intf = RescueInterface(screen)

    # prompt to see if we should try and find root filesystem and mount
    # everything in /etc/fstab on that root
    rc = ButtonChoiceWindow(screen, _("Rescue"),
        _("The rescue environment will now attempt to find your Red Hat "
          "Linux installation and mount it under the directory "
          "/mnt/sysimage.  You can then make any changes required to your "
          "system.  If you want to proceed with this step choose "
          "'Continue'.\n\n"
          "If for some reason this process fails you can choose 'Skip' "
          "and this step will be skipped and you will go directly to a "
          "command shell.\n\n"),
          [_("Continue"), _("Skip")] )

    if rc == string.lower(_("Skip")):
        screen.finish()
        print
        print _("When finished please exit from the shell and your "
                "system will reboot.")
        print
        os.execv("/bin/sh", [ "-/bin/sh" ])

    disks = upgrade.findExistingRoots(intf, id, instPath)

    if not disks:
	root = None
    elif len(disks) == 1:
	root = disks[0]
    else:
	height = min (len (disks), 12)
	if height == 12:
	    scroll = 1
	else:
	    scroll = 0

	partList = []
	for (drive, fs) in disks:
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
	    root = disks[choice]

    rootmounted = 0
    if root:
	try:
	    fs = fsset.FileSystemSet()
	    upgrade.mountRootPartition(intf, root, fs, instPath,
				       allowDirty = 1)
	    ButtonChoiceWindow(screen, _("Rescue"),
		_("Your system has been mounted under /mnt/sysimage.\n\n"
		  "Press <return> to get a shell. If you would like to "
		  "make your system the root environment, run the command:\n\n"
		  "\tchroot /mnt/sysimage\n\nThe system will reboot "
		  "automatically when you exit from the shell."),
		  [_("OK")] )
            rootmounted = 1
	except:
	    # This looks horrible, but all it does is catch every exception,
	    # and reraise those in the tuple check. This lets programming
	    # errors raise exceptions, while any runtime error will
	    # still result in a shell. 
	    (exc, val) = sys.exc_info()[0:2]
	    #if exc in (IndexError, ValueError, SyntaxError):
	    if 1:
		raise exc, val, sys.exc_info()[2]

	    ButtonChoiceWindow(screen, _("Rescue"),
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
			   [ _("OK") ], width = 50)

    screen.finish()

    print
    if rootmounted:
        print _("Your system is mounted under the /mnt/sysimage directory.")
        print

    print _("When finished please exit from the shell and your "
                "system will reboot.")
    print
    os.execv("/bin/sh", [ "-/bin/sh" ])
