#
# rescue.py - anaconda rescue mode setup
#
# Mike Fulbright <msf@redhat.com>
#
# Copyright 2001-2002 Red Hat, Inc.
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
from constants_text import *
from text import WaitWindow, OkCancelWindow, ProgressWindow
import sys
import os
import isys
import iutil
import fsset

from rhpl.log import log
from rhpl.translate import _

class RescueInterface:
    def waitWindow(self, title, text):
	return WaitWindow(self.screen, title, text)

    def progressWindow(self, title, text, total):
	return ProgressWindow(self.screen, title, text, total)
	
    def messageWindow(self, title, text, type = "ok"):
	if type == "ok":
	    ButtonChoiceWindow(self.screen, _(title), _(text),
			       buttons = [ _("OK") ])
        elif type == "yesno":
            btnlist = [TEXT_YES_BUTTON, TEXT_NO_BUTTON]
	    rc = ButtonChoiceWindow(self.screen, _(title), _(text),
			       buttons=btnlist)
            if rc == "yes":
                return 1
            else:
                return 0
	else:
	    return OkCancelWindow(self.screen, _(title), _(text))

    def __init__(self, screen):
	self.screen = screen

# XXX grub-install is stupid and uses df output to figure out
# things when installing grub.  make /etc/mtab be at least
# moderately useful.  
def makeMtab(instPath, theFsset):
    child = os.fork()
    if (not child):
        os.chroot(instPath)
        f = open("/etc/mtab", "w+")
        f.write(theFsset.mtab())
        f.close()
        sys.exit(0)

# XXX
#     probably belongs somewhere else
#
def methodUsesNetworking(methodstr):
    for m in ['http://', 'ftp://', 'nfs://', 'nfsiso://']:
	if methodstr.startswith(m):
	    return 1
    return 0

# XXX
#     hack to write out something useful for networking and start interfaces
#
def startNetworking(network):

    # do lo first
    try:
	os.system("/usr/bin/ifconfig lo 127.0.0.1")
    except:
	log("Error trying to start lo in rescue.py::startNetworking()")

    # start up dhcp interfaces first
    dhcpGotNS = 0
    for devname in network.netdevices:
	dev = network.netdevices[devname]
	log("Attempting to start %s", dev.get('device'))
	if dev.get('bootproto') == "dhcp":
	    try:
		ns = isys.pumpNetDevice(dev.get('device'))
		if ns:
		    if not dhcpGotNS:
			dhcpGotNS = 1

			f = open("/etc/resolv.conf", "w")
			f.write("nameserver %s\n" % ns)
			f.close()
	    except:
		log("Error trying to start %s in rescue.py::startNetworking()", dev.get('device'))
	elif dev.get('ipaddr') and dev.get('netmask') and network.gateway is not None:
	    try:
		isys.configNetDevice(dev.get('device'),
				     dev.get('ipaddr'),
				     dev.get('netmask'),
				     network.gateway)
	    except:
		log("Error trying to start %s in rescue.py::startNetworking()", dev.get('device'))
		    
    # write out resolv.conf if dhcp didnt get us one
    if not dhcpGotNS:
        f = open("/etc/resolv.conf", "w")

	if network.domains != ['localdomain'] and network.domains:
	    f.write("search %s\n" % (string.joinfields(network.domains, ' '),))

        for ns in network.nameservers():
            if ns:
                f.write("nameserver %s\n" % (ns,))

        f.close()
	
    
def runRescue(instPath, mountroot, id):

    for file in [ "services", "protocols", "group" ]:
       os.symlink('/mnt/runtime/etc/' + file, '/etc/' + file)

    # see if they would like networking enabled
    if not methodUsesNetworking(id.methodstr):
	import network_text
	
	screen = SnackScreen()

	rc = ButtonChoiceWindow(screen, _("Setup Networking"),
	    _("Do you want to start the network interfaces on this system?"),
				[_("Yes"), _("No")])

	if rc != string.lower(_("No")):
	    intf = RescueInterface(screen)

	    window = network_text.NetworkWindow()
	    rc = apply(window, (screen, id.network, intf, 1))
	    startNetworking(id.network)

	screen.finish()

    if (not mountroot):
        print
        print _("When finished please exit from the shell and your "
                "system will reboot.")
        print
	os.execv("/bin/sh", [ "-/bin/sh" ])

    # lets create some devices
    iutil.makeDriveDeviceNodes()

    # need loopback devices too
    for lpminor in range(8):
	dev = "loop%s" % (lpminor,)
	isys.makeDevInode(dev, "/dev/" + dev)

    screen = SnackScreen()
    intf = RescueInterface(screen)

    # prompt to see if we should try and find root filesystem and mount
    # everything in /etc/fstab on that root
    rc = ButtonChoiceWindow(screen, _("Rescue"),
        _("The rescue environment will now attempt to find your Red Hat "
          "Linux installation and mount it under the directory "
          "%s.  You can then make any changes required to your "
          "system.  If you want to proceed with this step choose "
          "'Continue'.  You can also choose to mount your file systems "
          "read-only instead of read-write by choosing 'Read-Only'."
          "\n\n"
          "If for some reason this process fails you can choose 'Skip' "
          "and this step will be skipped and you will go directly to a "
          "command shell.\n\n" % (instPath,)),
          [_("Continue"), _("Read-Only"), _("Skip")] )

    if rc == string.lower(_("Skip")):
        screen.finish()
        print
        print _("When finished please exit from the shell and your "
                "system will reboot.")
        print
        os.execv("/bin/sh", [ "-/bin/sh" ])
    elif rc == string.lower(_("Read-Only")):
        readOnly = 1
    else:
        readOnly = 0

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

	    # only pass first two parts of tuple for root, since third
	    # element is a comment we dont want
	    rc = upgrade.mountRootPartition(intf, root[:2],
					    fs, instPath,
                                            allowDirty = 1, warnDirty = 1,
                                            readOnly = readOnly)

            if rc == -1:
                ButtonChoiceWindow(screen, _("Rescue"),
                    _("Your system had dirty file systems which you chose not "
                      "to mount.  Press return to get a shell from which "
                      "you can fsck and mount your partitions.  The system "
                      "will reboot automatically when you exit from the "
                      "shell."), [_("OK")], width = 50)
                rootmounted = 0
            else:
                ButtonChoiceWindow(screen, _("Rescue"),
		   _("Your system has been mounted under %s.\n\n"
                     "Press <return> to get a shell. If you would like to "
                     "make your system the root environment, run the command:\n\n"
                     "\tchroot %s\n\nThe system will reboot "
                     "automatically when you exit from the shell.") %
                                   (instPath,instPath),
                                   [_("OK")] )
                rootmounted = 1

		# now turn on swap
		if not readOnly:
		    try:
			fs.turnOnSwap("/")
		    except:
			log("Error enabling swap")

		# set a library path to use mounted fs
		os.environ["LD_LIBRARY_PATH"] =  "/lib:/usr/lib:/usr/X11R6/lib:/usr/kerberos/lib:/mnt/usr/lib:/mnt/sysimage/lib:/mnt/sysimage/usr/lib:/mnt/sysimage/usr/kerberos/lib"
		    
	except:
	    # This looks horrible, but all it does is catch every exception,
	    # and reraise those in the tuple check. This lets programming
	    # errors raise exceptions, while any runtime error will
	    # still result in a shell. 
	    (exc, val) = sys.exc_info()[0:2]
	    if exc in (IndexError, ValueError, SyntaxError):
		raise exc, val, sys.exc_info()[2]

	    ButtonChoiceWindow(screen, _("Rescue"),
		_("An error occurred trying to mount some or all of your "
		  "system. Some of it may be mounted under %s.\n\n"
		  "Press <return> to get a shell. The system will reboot "
		  "automatically when you exit from the shell." % (instPath,)),
		  [_("OK")] )
    else:
	ButtonChoiceWindow(screen, _("Rescue Mode"),
			   _("You don't have any Linux partitions. Press "
			     "return to get a shell. The system will reboot "
			     "automatically when you exit from the shell."),
			   [ _("OK") ], width = 50)

    screen.finish()

    print
    if rootmounted and not readOnly:
        makeMtab(instPath, fs)
        print _("Your system is mounted under the %s directory." % (instPath,))
        print

    print _("When finished please exit from the shell and your "
                "system will reboot.")
    print
    os.execv("/bin/sh", [ "-/bin/sh" ])
