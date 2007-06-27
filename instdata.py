#
# instdata.py - central store for all configuration data needed to install
#
# Erik Troan <ewt@redhat.com>
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
from flags import *
from constants import *

from rhpl.simpleconfig import SimpleConfigFile
import rhpl.keyboard as keyboard

import logging
log = logging.getLogger("anaconda")

# Collector class for all data related to an install/upgrade.

class InstallData:

    def reset(self, anaconda):
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
        self.users = None
        self.rootPassword = { "isCrypted": False, "password": "" }
	self.auth = "--enableshadow --enablemd5"
	self.desktop = desktop.Desktop()
	self.upgrade = None
        # XXX move fsset and/or diskset into Partitions object?
	self.fsset.reset()
        self.diskset = partedUtils.DiskSet(anaconda)
        self.partitions = partitions.Partitions()
        self.bootloader = bootloader.getBootloader()
        self.dependencies = []
        self.dbpath = None
        self.upgradeRoot = None
        self.rootParts = None
        self.upgradeSwapInfo = None
        self.upgradeDeps = ""
        self.upgradeRemove = []
        self.upgradeInfoFound = None

        if rhpl.getArch() == "s390":
            self.firstboot = FIRSTBOOT_SKIP
        else:
            self.firstboot = FIRSTBOOT_DEFAULT

        # XXX I expect this to die in the future when we have a single data
        # class and translate ksdata into that instead.
        self.ksdata = None

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

    def write(self, anaconda):
        if self.auth.find("--enablemd5"):
            useMD5 = True
        else:
            useMD5 = False

        self.instLanguage.write (anaconda.rootPath)

        if not self.isHeadless:
            self.keyboard.write (anaconda.rootPath)
            
        self.timezone.write (anaconda.rootPath)

        args = ["--update", "--nostart"] + self.auth.split()

        try:
            if not flags.test:
                iutil.execWithRedirect("/usr/sbin/authconfig", args,
                                       stdout = None, stderr = None,
                                       root = anaconda.rootPath)
            else:
                log.error("Would have run: %s", args)
        except RuntimeError, msg:
                log.error("Error running %s: %s", args, msg)
	
	self.firewall.write (anaconda.rootPath)
        self.security.write (anaconda.rootPath)

        self.users = users.Users()

        # User should already exist, just without a password.
        self.users.setRootPassword(self.rootPassword["password"],
                                   self.rootPassword["isCrypted"], useMD5)

        # Make sure multipathd is set to run for mpath installs (#243421)
        if flags.mpath:
            svc = 'multipathd'

            if anaconda.isKickstart:
                try:
                    hasSvc = self.ksdata.services["enabled"].index(svc)
                except:
                    self.ksdata.services["enabled"].append(svc)
            else:
                iutil.execWithRedirect("/sbin/chkconfig",
                                       [svc, "on"],
                                       stdout="/dev/tty5", stderr="/dev/tty5",
                                       root=anaconda.rootPath)

        if anaconda.isKickstart:
            for svc in self.ksdata.services["disabled"]:
                iutil.execWithRedirect("/sbin/chkconfig",
                                       [svc, "off"],
                                       stdout="/dev/tty5", stderr="/dev/tty5",
                                       root=anaconda.rootPath)

            for svc in self.ksdata.services["enabled"]:
                iutil.execWithRedirect("/sbin/chkconfig",
                                       [svc, "on"],
                                       stdout="/dev/tty5", stderr="/dev/tty5",
                                       root=anaconda.rootPath)

            for ud in self.ksdata.userList:
                if self.users.createUser(ud.name, ud.password, ud.isCrypted,
                                         ud.groups, ud.homedir, ud.shell,
                                         ud.uid, root=anaconda.rootPath) == None:
                    log.error("User %s already exists, not creating." % ud.name)

        if anaconda.id.instClass.installkey and os.path.exists(anaconda.rootPath + "/etc/sysconfig/rhn"):
            f = open(anaconda.rootPath + "/etc/sysconfig/rhn/install-num", "w+")
            f.write("%s\n" %(anaconda.id.instClass.installkey,))
            f.close()
            os.chmod(anaconda.rootPath + "/etc/sysconfig/rhn/install-num",
                     0600)

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
	if self.methodstr.startswith('ftp://') or self.methodstr.startswith('http://'):
	    f.write("url --url %s\n" % urllib.unquote(self.methodstr))
	elif self.methodstr.startswith('cdrom://'):
	    f.write("cdrom\n")
	elif self.methodstr.startswith('hd://'):
	    pidx = string.find(self.methodstr, '//') + 2
	    didx = string.find(self.methodstr[pidx:], '/')
	    partition = string.split(self.methodstr[pidx:pidx+didx], ':')[0]
	    dir = self.methodstr[pidx+didx+1:]
	    f.write("harddrive --partition=%s --dir=%s\n" % (partition, dir))
	elif self.methodstr.startswith('nfs:/') or self.methodstr.startswith('nfsiso:'):
	    (method, tmpmntpt) = string.split(self.methodstr, ':')
	    # clean up extra '/' at front
	    if tmpmntpt[1] == '/':
		rawmntpt = tmpmntpt[1:]
	    else:
		rawmntpt = tmpmntpt
	    mntpt = os.path.normpath(rawmntpt)

	    # find mntpt in /proc/mounts so we can get NFS server info
	    fproc = open("/proc/mounts", "r")
	    lines = fproc.readlines()
	    fproc.close()

	    for l in lines:
		minfo = string.split(l)
                if len(minfo) > 1 and minfo[1] == mntpt and minfo[0].find(":") != -1:
		    (srv, dir) = minfo[0].split(':')
		    f.write("nfs --server=%s --dir=%s\n" % (srv, dir))
		    break

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
        self.iscsi.writeKS(f)

        if self.rootPassword["isCrypted"]:
            f.write("rootpw --iscrypted %s\n" % self.rootPassword["password"])
        else:
            f.write("rootpw --iscrypted %s\n" % users.cryptPassword(self.rootPassword["password"], useMD5))

	self.firewall.writeKS(f)
	if self.auth.strip() != "":
	    f.write("authconfig %s\n" % self.auth)
        self.security.writeKS(f)
	self.timezone.writeKS(f)
        self.bootloader.writeKS(f)
        self.partitions.writeKS(f)
        if self.backend is not None:
            self.backend.writePackagesKS(f)

        # make it so only root can read, could have password
        os.chmod(filename, 0600)


    def __init__(self, anaconda, extraModules, floppyDevice, methodstr, displayMode, backend = None):
        self.displayMode = displayMode

	self.instLanguage = language.Language(self.displayMode)
	self.keyboard = keyboard.Keyboard()
        self.backend = backend

        self.mouse = None
        self.monitor = None
        self.videocard = None
        self.xsetup = None
        self.isHeadless = 0
	self.extraModules = extraModules
	self.floppyDevice = floppyDevice
	self.fsset = fsset.FileSystemSet(anaconda)
        self.excludeDocs = 0

        if flags.cmdline.has_key("excludedocs"):
            self.excludeDocs = 1

        self.methodstr = methodstr
	self.reset(anaconda)
