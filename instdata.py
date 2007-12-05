#
# instdata.py - central store for all configuration data needed to install
#
# Erik Troan <ewt@redhat.com>
#
# Copyright 2001-2007 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import os
import string
import language
import network
import firewall
import security
import timezone
import desktop
import fsset
import bootloader
import partitions
import partedUtils
import iscsi
import zfcp
import urllib
import iutil
import users
import rhpl
import shlex
from flags import *
from constants import *

from rhpl.simpleconfig import SimpleConfigFile
import rhpl.keyboard as keyboard

import logging
log = logging.getLogger("anaconda")

# Collector class for all data related to an install/upgrade.

class InstallData:

    def reset(self):
	# Reset everything except: 
	#
	#	- The mouse
	#	- The install language
	#	- The keyboard

	self.instClass = None
	self.network = network.Network()
	self.iscsi = iscsi.iscsi()
	self.zfcp = zfcp.ZFCP()
	self.firewall = firewall.Firewall()
        self.security = security.Security()
	self.timezone = timezone.Timezone()
        self.timezone.setTimezoneInfo(self.instLanguage.getDefaultTimeZone())
        self.users = None
        self.rootPassword = { "isCrypted": False, "password": "", "lock": False }
	self.auth = "--enableshadow --enablemd5"
	self.desktop = desktop.Desktop()
        self.upgrade = None
        if flags.cmdline.has_key("doupgrade"):
            self.upgrade = True
        # XXX move fsset and/or diskset into Partitions object?
	self.fsset.reset()
        self.diskset = partedUtils.DiskSet(self.anaconda)
        self.partitions = partitions.Partitions(self.anaconda)
        self.bootloader = bootloader.getBootloader()
        self.upgradeRoot = None
        self.rootParts = None
        self.upgradeSwapInfo = None

        if rhpl.getArch() == "s390" or self.anaconda.isKickstart:
            self.firstboot = FIRSTBOOT_SKIP
        else:
            self.firstboot = FIRSTBOOT_DEFAULT

        # XXX I still expect this to die when kickstart is the data store.
        self.ksdata = None

        # We don't have install methods anymore, but put things that depend on
        # the methodstr here.
        if os.path.exists("/dev/live") and \
           stat.S_ISBLK(os.stat("/dev/live")[stat.ST_MODE]):
            target = os.readlink("/dev/live")
            self.partitions.protected = [target]
        elif self.methodstr.startswith("hd://"):
            method = self.methodstr[5:]
            device = method.split(":", 3)[0]
            self.partitions.protected = [device]

    def setInstallProgressClass(self, c):
	self.instProgress = c

    def setDisplayMode(self, display_mode):
	self.displayMode = display_mode

    # expects a Keyboard object
    def setKeyboard(self, keyboard):
        self.keyboard = keyboard

    # expects a Mouse object
    def setMouse(self, mouse):
        self.mouse = mouse

    # expects a VideoCardInfo object
    def setVideoCard(self, video):
        self.videocard = video

    # expects a Monitor object
    def setMonitor(self, monitor):
        self.monitor = monitor

    # expects an XSetup object
    def setXSetup(self, xsetup):
        self.xsetup = xsetup

    # expects 0/1
    def setHeadless(self, isHeadless):
        self.isHeadless = isHeadless

    def setKsdata(self, ksdata):
        self.ksdata = ksdata

    # if upgrade is None, it really means False.  we use None to help the
    # installer ui figure out if it's the first time the user has entered
    # the examine_gui screen.   --dcantrell
    def getUpgrade (self):
        if self.upgrade == None:
            return False
        else:
            return self.upgrade

    def setUpgrade (self, bool):
        self.upgrade = bool

    def write(self):
        if self.auth.find("--enablemd5"):
            useMD5 = True
        else:
            useMD5 = False

        self.instLanguage.write (self.anaconda.rootPath)

        if not self.isHeadless:
            self.keyboard.write (self.anaconda.rootPath)

        self.timezone.write (self.anaconda.rootPath)

        args = ["--update", "--nostart"] + shlex.split(self.auth)

        try:
            if not flags.test:
                iutil.execWithRedirect("/usr/sbin/authconfig", args,
                                       stdout = None, stderr = None,
                                       root = self.anaconda.rootPath)
            else:
                log.error("Would have run: %s", args)
        except RuntimeError, msg:
                log.error("Error running %s: %s", args, msg)

	self.network.write (self.anaconda.rootPath)
	self.firewall.write (self.anaconda.rootPath)
        self.security.write (self.anaconda.rootPath)

        self.users = users.Users()

        # User should already exist, just without a password.
        self.users.setRootPassword(self.rootPassword["password"],
                                   self.rootPassword["isCrypted"], useMD5,
                                   self.rootPassword["lock"])

        if self.anaconda.isKickstart:
            for svc in self.ksdata.services.disabled:
                iutil.execWithRedirect("/sbin/chkconfig",
                                       [svc, "off"],
                                       stdout="/dev/tty5", stderr="/dev/tty5",
                                       root=self.anaconda.rootPath)

            for svc in self.ksdata.services.enabled:
                iutil.execWithRedirect("/sbin/chkconfig",
                                       [svc, "on"],
                                       stdout="/dev/tty5", stderr="/dev/tty5",
                                       root=self.anaconda.rootPath)

            for ud in self.ksdata.user.userList:
                if self.users.createUser(ud.name, ud.password, ud.isCrypted,
                                         ud.groups, ud.homedir, ud.shell,
                                         ud.uid, ud.lock,
                                         root=self.anaconda.rootPath) == None:
                    log.error("User %s already exists, not creating." % ud.name)


    def writeKS(self, filename):
        if self.auth.find("--enablemd5"):
            useMD5 = True
        else:
            useMD5 = False

	f = open(filename, "w")

	f.write("# Kickstart file automatically generated by anaconda.\n\n")
	if self.upgrade:
	    f.write("upgrade\n");
	else:
	    f.write("install\n");

	# figure out the install method and write out a line
        self.anaconda.writeMethodstr(f)

        if self.instClass.skipkey:
            f.write("key --skip\n")
        elif self.instClass.installkey:
            f.write("key %s\n" %(self.instClass.installkey,))

	self.instLanguage.writeKS(f)
        if not self.isHeadless:
            self.keyboard.writeKS(f)
            self.xsetup.writeKS(f, self.desktop, self.ksdata)
	self.network.writeKS(f)
	self.zfcp.writeKS(f)

        if self.rootPassword["isCrypted"]:
            args = " --iscrypted %s" % self.rootPassword["password"]
        else:
            args = " --iscrypted %s" % users.cryptPassword(self.rootPassword["password"], useMD5)

        if self.rootPassword["lock"]:
            args += " --lock"

        f.write("rootpw %s\n" % args)

        # Some kickstart commands do not correspond to any anaconda UI
        # component.  If this is a kickstart install, we need to make sure
        # the information from the input file ends up in the output file.
        if self.anaconda.isKickstart:
            f.write(self.ksdata.user.__str__())
            f.write(self.ksdata.services.__str__())
            f.write(self.ksdata.reboot.__str__())

	self.firewall.writeKS(f)
	if self.auth.strip() != "":
	    f.write("authconfig %s\n" % self.auth)
        self.security.writeKS(f)
	self.timezone.writeKS(f)
        self.bootloader.writeKS(f)
        self.partitions.writeKS(f)

        if self.backend is not None:
            self.backend.writeKS(f)
            self.backend.writePackagesKS(f, self.anaconda)

        # Also write out any scripts from the input ksfile.
        if self.anaconda.isKickstart:
            for s in self.ksdata.scripts:
                f.write(s.__str__())

        # make it so only root can read, could have password
        os.chmod(filename, 0600)


    def __init__(self, anaconda, extraModules, methodstr, displayMode, backend = None):
        self.displayMode = displayMode

	self.instLanguage = language.Language(self.displayMode)
	self.keyboard = keyboard.Keyboard()
        self.backend = backend
        self.anaconda = anaconda

        self.mouse = None
        self.monitor = None
        self.videocard = None
        self.xsetup = None
        self.isHeadless = 0
	self.extraModules = extraModules
	self.fsset = fsset.FileSystemSet()

        self.methodstr = methodstr
	self.reset()
