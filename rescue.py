#
# rescue.py - anaconda rescue mode setup
#
# Mike Fulbright <msf@redhat.com>
# Jeremy Katz <katzj@redhat.com>
#
# Copyright 2001-2004 Red Hat, Inc.
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
from text import WaitWindow, OkCancelWindow, ProgressWindow, PassphraseEntryWindow, stepToClasses
from flags import flags
import sys
import os
import isys
import iutil
import fsset
import shutil
import fcntl
import termios
import time

from rhpl.translate import _

import logging
log = logging.getLogger("anaconda")

class RescueInterface:
    def waitWindow(self, title, text):
	return WaitWindow(self.screen, title, text)

    def progressWindow(self, title, text, total):
	return ProgressWindow(self.screen, title, text, total)
	
    def messageWindow(self, title, text, type="ok", default = None,
		      custom_icon=None, custom_buttons=[]):
	if type == "ok":
	    ButtonChoiceWindow(self.screen, title, text,
			       buttons=[TEXT_OK_BUTTON])
        elif type == "yesno":
            if default and default == "no":
                btnlist = [TEXT_NO_BUTTON, TEXT_YES_BUTTON]
            else:
                btnlist = [TEXT_YES_BUTTON, TEXT_NO_BUTTON]
	    rc = ButtonChoiceWindow(self.screen, title, text,
			       buttons=btnlist)
            if rc == "yes":
                return 1
            else:
                return 0
	elif type == "custom":
	    tmpbut = []
	    for but in custom_buttons:
		tmpbut.append(string.replace(but,"_",""))

	    rc = ButtonChoiceWindow(self.screen, title, text, width=60,
				    buttons=tmpbut)

	    idx = 0
	    for b in tmpbut:
		if string.lower(b) == rc:
		    return idx
		idx = idx + 1
	    return 0
	else:
	    return OkCancelWindow(self.screen, title, text)

    def passphraseEntryWindow(self, device):
        w = PassphraseEntryWindow(self.screen, device)
        (passphrase, isglobal) = w.run()
        w.pop()
        return (passphrase, isglobal)

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
        os._exit(0)

# make sure they have a resolv.conf in the chroot
def makeResolvConf(instPath):
    if not os.access("/etc/resolv.conf", os.R_OK):
        return
    
    if os.access("%s/etc/resolv.conf" %(instPath,), os.R_OK):
        f = open("%s/etc/resolv.conf" %(instPath,), "r")
        buf = f.read()
        f.close()
    else:
        buf = ""

    # already have a nameserver line, don't worry about it
    if buf.find("nameserver") != -1:
        return

    f = open("/etc/resolv.conf", "r")
    buf = f.read()
    f.close()

    # no nameserver, we can't do much about it
    if buf.find("nameserver") == -1:
        return

    shutil.copyfile("%s/etc/resolv.conf" %(instPath,),
                    "%s/etc/resolv.conf.bak" %(instPath,))
    f = open("%s/etc/resolv.conf" %(instPath,), "w+")
    f.write(buf)
    f.close()

# XXX
#     probably belongs somewhere else
#
def methodUsesNetworking(methodstr):
    for m in ['http://', 'ftp://', 'nfs:/', 'nfsiso:/']:
	if methodstr.startswith(m):
	    return 1
    return 0

# XXX
#     hack to write out something useful for networking and start interfaces
#
def startNetworking(network, intf, anaconda):

    # do lo first
    try:
	os.system("/usr/sbin/ifconfig lo 127.0.0.1")
    except:
	log.error("Error trying to start lo in rescue.py::startNetworking()")

    # start up dhcp interfaces first
    dhcpGotNS = 0
    devs = network.netdevices.keys()
    devs.sort()
    for devname in devs:
	dev = network.netdevices[devname]
	waitwin = intf.waitWindow(_("Starting Interface"),
				  _("Attempting to start %s") % (dev.get('device'),))
	log.info("Attempting to start %s", dev.get('device'))
        method = dev.get('bootproto')
        while True:
            if method == "ibft":
                try:
                    if anaconda.id.iscsi.fwinfo["iface.bootproto"].lower() == "dhcp":
                        method = "dhcp"
                        continue
                    else:
                        hwaddr = isys.getMacAddress(dev)
                        if hwaddr != anaconda.id.iscsi.fwinfo["iface.hwaddress"]:
                            log.error("The iBFT configuration does not belong to device %s,"
                                      "falling back to dhcp", dev.get('device'))
                            method = "dhcp"
                            continue

                        isys.configNetDevice(dev.get('device'),
                                             anaconda.id.iscsi.fwinfo["iface.ipaddress"],
                                             anaconda.id.iscsi.fwinfo["iface.subnet_mask"],
                                             anaconda.id.iscsi.fwinfo["iface.gateway"])
                except:
                    log.error("failed to configure network device %s using "
                              "iBFT information, falling back to dhcp", dev.get('device'))
                    usemethod = "dhcp"
                    continue
            elif method == "dhcp":
                try:
                    ns = isys.dhcpNetDevice(dev.get('device'))
                    if ns:
                        if not dhcpGotNS:
                            dhcpGotNS = 1

                            f = open("/etc/resolv.conf", "w")
                            f.write("nameserver %s\n" % ns)
                            f.close()
                except:
                    log.error("Error trying to start %s in rescue.py::startNetworking()", dev.get('device'))
            elif dev.get('ipaddr') and dev.get('netmask') and network.gateway is not None:
                try:
                    isys.configNetDevice(dev.get('device'),
                                         dev.get('ipaddr'),
                                         dev.get('netmask'),
                                         network.gateway)
                except:
                    log.error("Error trying to start %s in rescue.py::startNetworking()", dev.get('device'))

            #do that only once
            break

	waitwin.pop()
	
    # write out resolv.conf if dhcp didnt get us one
    if not dhcpGotNS:
        f = open("/etc/resolv.conf", "w")

	if network.domains != ['localdomain'] and network.domains:
	    f.write("search %s\n" % (string.joinfields(network.domains, ' '),))

        for ns in network.nameservers():
            if ns:
                f.write("nameserver %s\n" % (ns,))

        f.close()

def runShell(screen = None, msg=""):
    if screen:
        screen.suspend()

    print
    if msg:
        print (msg)
    print _("When finished please exit from the shell and your "
            "system will reboot.")
    print

    if os.path.exists("/bin/sh"):
        iutil.execConsole()
    else:
        print "Unable to find /bin/sh to execute!  Not starting shell"
        time.sleep(5)

    if screen:
        screen.finish()

def runRescue(anaconda):
    for file in [ "services", "protocols", "group", "joe", "man.config",
                  "nsswitch.conf", "selinux", "mke2fs.conf" ]:
        try:
            os.symlink('/mnt/runtime/etc/' + file, '/etc/' + file)
        except:
            pass

    # see if they would like networking enabled
    if not methodUsesNetworking(anaconda.id.methodstr):
	screen = SnackScreen()

	while 1:
	    rc = ButtonChoiceWindow(screen, _("Setup Networking"),
		_("Do you want to start the network interfaces on "
		  "this system?"), [_("Yes"), _("No")])

	    if rc != string.lower(_("No")):
		anaconda.intf = RescueInterface(screen)

		# need to call sequence of screens, have to look in text.py
		#
		# this code is based on main loop in text.py, and if it
		# or the network step in dispatch.py change significantly
		# then this will certainly break
		#
                pyfile = "network_text"
		classNames = ("NetworkDeviceWindow", "NetworkGlobalWindow")

		lastrc = INSTALL_OK
		step = 0
		anaconda.dir = 1

		while 1:
		    s = "from %s import %s; nextWindow = %s" % \
			(pyfile, classNames[step], classNames[step])
		    exec s

		    win = nextWindow()

                    rc = win(screen, anaconda, showonboot = 0)

		    if rc == INSTALL_NOOP:
			rc = lastrc
			
		    if rc == INSTALL_BACK:
			step = step - 1
			anaconda.dir = - 1
		    elif rc == INSTALL_OK:
			step = step + 1
			anaconda.dir = 1

		    lastrc = rc

		    if step == -1:
			ButtonChoiceWindow(screen, _("Cancelled"),
					   _("I can't go to the previous step "
					     "from here. You will have to try "
					     "again."),
					   buttons=[_("OK")])
                        anaconda.dir = 1
                        step = 0
		    elif step >= len(classNames):
			break

		startNetworking(anaconda.id.network, anaconda.intf, anaconda)
		break
	    else:
		break

	screen.finish()

    # Early shell access with no disk access attempts
    if not anaconda.rescue_mount:
	runShell()
	sys.exit(0)

    # need loopback devices too
    for lpminor in range(8):
	dev = "loop%s" % (lpminor,)
	isys.makeDevInode(dev, "/dev/" + dev)

    screen = SnackScreen()
    anaconda.intf = RescueInterface(screen)
    anaconda.setMethod()

    # prompt to see if we should try and find root filesystem and mount
    # everything in /etc/fstab on that root
    rc = ButtonChoiceWindow(screen, _("Rescue"),
        _("The rescue environment will now attempt to find your "
          "Linux installation and mount it under the directory "
          "%s.  You can then make any changes required to your "
          "system.  If you want to proceed with this step choose "
          "'Continue'.  You can also choose to mount your file systems "
          "read-only instead of read-write by choosing 'Read-Only'."
          "\n\n"
          "If for some reason this process fails you can choose 'Skip' "
          "and this step will be skipped and you will go directly to a "
          "command shell.\n\n") % (anaconda.rootPath,),
          [_("Continue"), _("Read-Only"), _("Skip")] )

    if rc == string.lower(_("Skip")):
        runShell(screen)
        sys.exit(0)
    elif rc == string.lower(_("Read-Only")):
        readOnly = 1
    else:
        readOnly = 0

    disks = upgrade.findExistingRoots(anaconda, upgradeany = 1)

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
	for (drive, fs, relstr, label) in disks:
            if label:
	        partList.append("%s (%s)" % (drive, label))
            else:
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
	    fs = fsset.FileSystemSet(anaconda)

	    # only pass first two parts of tuple for root, since third
	    # element is a comment we dont want
	    rc = upgrade.mountRootPartition(anaconda, root[:2], fs,
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
                                   (anaconda.rootPath, anaconda.rootPath),
                                   [_("OK")] )
                rootmounted = 1

		# now turn on swap
		if not readOnly:
		    try:
			fs.turnOnSwap("/")
		    except:
			log.error("Error enabling swap")

                # now that dev is udev, bind mount the installer dev there
                isys.mount("/dev", "%s/dev" %(anaconda.rootPath,), bindMount = 1)

                # and /dev/pts
                isys.mount("/dev/pts", "%s/dev/pts" %(anaconda.rootPath,), bindMount = 1)

                # and /selinux too
                if flags.selinux and os.path.isdir("%s/selinux" %(anaconda.rootPath,)):
                    try:
                        isys.mount("/selinux", "%s/selinux" %(anaconda.rootPath,),
                                   "selinuxfs")
                    except Exception, e:
                        log.error("error mounting selinuxfs: %s" %(e,))

		# set a library path to use mounted fs
		os.environ["LD_LIBRARY_PATH"] =  "/lib:/usr/lib:/usr/X11R6/lib:/lib:/mnt/usr/lib:/mnt/sysimage/lib:/mnt/sysimage/usr/lib:/mnt/sysimage/usr/X11R6/lib"

		# get man pages to work
                os.environ["MANPATH"] = "/mnt/sysimage/usr/share/man:/mnt/sysimage/usr/local/share/man:/usr/share/man:/usr/local/share/man"

		# find groff data dir
		try:
		    glst = os.listdir("/mnt/sysimage/usr/share/groff")

		    # find a directory which is a numeral, its where
		    # data files are
		    gversion = None
		    for gdir in glst:
			try:
			    isone = 1
			    for idx in range(0, len(gdir)):
				if string.find(string.digits + '.', gdir[idx]) == -1:
				    isone = 0
				    break
			    if isone:
				gversion = gdir
				break
				
			except:
			    gversion = None
			    continue
			
		except:
		    gversion = None

		if gversion is not None:
		    gpath = "/mnt/sysimage/usr/share/groff/"+gversion
		    os.environ["GROFF_FONT_PATH"] = gpath + '/font'
		    os.environ["GROFF_TMAC_PATH"] = "%s:/mnt/sysimage/usr/share/groff/site-tmac" % (gpath + '/tmac',)
		    

		# do we have bash?
		try:
		    if os.access("/usr/bin/bash", os.R_OK):
			os.symlink ("/usr/bin/bash", "/bin/bash")
		except:
		    pass
		    
			
	except:
	    # This looks horrible, but all it does is catch every exception,
	    # and reraise those in the tuple check. This lets programming
	    # errors raise exceptions, while any runtime error will
	    # still result in a shell. 
	    (exc, val) = sys.exc_info()[0:2]
            log.error(val)
	    if exc in (IndexError, ValueError, SyntaxError):
		raise exc, val, sys.exc_info()[2]

	    ButtonChoiceWindow(screen, _("Rescue"),
		_("An error occurred trying to mount some or all of your "
		  "system. Some of it may be mounted under %s.\n\n"
		  "Press <return> to get a shell. The system will reboot "
		  "automatically when you exit from the shell.") % (anaconda.rootPath,),
		  [_("OK")] )
    else:
	ButtonChoiceWindow(screen, _("Rescue Mode"),
			   _("You don't have any Linux partitions. Press "
			     "return to get a shell. The system will reboot "
			     "automatically when you exit from the shell."),
			   [ _("OK") ], width = 50)

    msgStr = ""

    if rootmounted and not readOnly:
        makeMtab(anaconda.rootPath, fs)
        try:
            makeResolvConf(anaconda.rootPath)
        except Exception, e:
            log.error("error making a resolv.conf: %s" %(e,))
        msgStr = _("Your system is mounted under the %s directory.") % (anaconda.rootPath,)

    runShell(screen, msgStr)
    sys.exit(0)
