#
# instdata.py - central store for all configuration data needed to install
#
# Copyright (C) 2001, 2002, 2003, 2004, 2005, 2006, 2007  Red Hat, Inc.
# All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Author(s): Erik Troan <ewt@redhat.com>
#            Chris Lumens <clumens@redhat.com>
#

import os, sys
import stat
import string
import language
import network
import firewall
import security
import timezone
import desktop
import booty
import storage
import urllib
import iutil
import isys
import users
import shlex
from flags import *
from constants import *
from simpleconfig import SimpleConfigFile
import system_config_keyboard.keyboard as keyboard

from pykickstart.version import versionToString, RHEL6

import logging
log = logging.getLogger("anaconda")

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

# Collector class for all data related to an install/upgrade.

class InstallData:

    def reset(self):
        # Reset everything except:
        #
        # - The install language
        # - The keyboard

        self.instClass = None
        self.network = network.Network()
        self.firewall = firewall.Firewall()
        self.security = security.Security()
        self.timezone = timezone.Timezone()
        self.timezone.setTimezoneInfo(self.instLanguage.getDefaultTimeZone(self.anaconda.rootPath))
        self.users = None
        self.rootPassword = { "isCrypted": False, "password": "", "lock": False }
        self.auth = "--enableshadow --passalgo=sha512 --enablefingerprint"
        self.desktop = desktop.Desktop()
        self.upgrade = None
        if flags.cmdline.has_key("preupgrade"):
            self.upgrade = True
        self.storage = storage.Storage(self.anaconda)
        self.bootloader = booty.getBootloader(self)
        self.upgradeRoot = None
        self.rootParts = None
        self.upgradeSwapInfo = None
        self.escrowCertificates = {}

        if iutil.isS390() or self.anaconda.isKickstart:
            self.firstboot = FIRSTBOOT_SKIP
        else:
            self.firstboot = FIRSTBOOT_DEFAULT

        # XXX I still expect this to die when kickstart is the data store.
        self.ksdata = None

    def setInstallProgressClass(self, c):
        self.instProgress = c

    def setDisplayMode(self, display_mode):
        self.displayMode = display_mode

    # expects a Keyboard object
    def setKeyboard(self, keyboard):
        self.keyboard = keyboard

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

    # Reads the auth string and returns a string indicating our desired
    # password encoding algorithm.
    def getPassAlgo(self):
        if self.auth.find("--enablemd5") != -1 or \
           self.auth.find("--passalgo=md5") != -1:
            return 'md5'
        elif self.auth.find("--passalgo=sha256") != -1:
            return 'sha256'
        elif self.auth.find("--passalgo=sha512") != -1:
            return 'sha512'
        else:
            return None

    def write(self):
        self.instLanguage.write (self.anaconda.rootPath)

        self.anaconda.writeXdriver(self.anaconda.rootPath)

        if not self.isHeadless:
            self.keyboard.write (self.anaconda.rootPath)

        self.timezone.write (self.anaconda.rootPath)

        args = ["--update", "--nostart"] + shlex.split(self.auth)

        try:
            iutil.execWithRedirect("/usr/sbin/authconfig", args,
                                   stdout = "/dev/tty5", stderr = "/dev/tty5",
                                   root = self.anaconda.rootPath)
        except RuntimeError, msg:
                log.error("Error running %s: %s", args, msg)

        self.network.write()
        self.network.copyConfigToPath(instPath=self.anaconda.rootPath)
        self.network.disableNMForStorageDevices(self.anaconda,
                                                instPath=self.anaconda.rootPath)
        self.firewall.write (self.anaconda.rootPath)
        self.security.write (self.anaconda.rootPath)
        self.desktop.write(self.anaconda.rootPath)

        self.users = users.Users()

        # make sure crypt_style in libuser.conf matches the salt we're using
        users.createLuserConf(self.anaconda.rootPath,
                              algoname=self.getPassAlgo())

        # User should already exist, just without a password.
        self.users.setRootPassword(self.rootPassword["password"],
                                   self.rootPassword["isCrypted"],
                                   self.rootPassword["lock"],
                                   algo=self.getPassAlgo())

        services = list(self.storage.services)

        if self.anaconda.isKickstart:
            services.extend(self.ksdata.services.enabled)

            for svc in self.ksdata.services.disabled:
                iutil.execWithRedirect("/sbin/chkconfig",
                                       [svc, "off"],
                                       stdout="/dev/tty5", stderr="/dev/tty5",
                                       root=self.anaconda.rootPath)

            for gd in self.ksdata.group.groupList:
                if not self.users.createGroup(name=gd.name,
                                              gid=gd.gid,
                                              root=self.anaconda.rootPath):
                    log.error("Group %s already exists, not creating." % gd.name)

            for ud in self.ksdata.user.userList:
                if not self.users.createUser(name=ud.name,
                                             password=ud.password,
                                             isCrypted=ud.isCrypted,
                                             groups=ud.groups,
                                             homedir=ud.homedir,
                                             shell=ud.shell,
                                             uid=ud.uid,
                                             algo=self.getPassAlgo(),
                                             lock=ud.lock,
                                             root=self.anaconda.rootPath,
                                             gecos=ud.gecos):
                    log.error("User %s already exists, not creating." % ud.name)

        for svc in services:
            iutil.execWithRedirect("/sbin/chkconfig",
                                   [svc, "on"],
                                   stdout="/dev/tty5", stderr="/dev/tty5",
                                   root=self.anaconda.rootPath)


    def writeKS(self, filename):
        f = open(filename, "w")

        f.write("# Kickstart file automatically generated by anaconda.\n\n")
        f.write("#version=%s\n" % versionToString(RHEL6))

        if self.upgrade:
            f.write("upgrade\n")
        else:
            f.write("install\n")

        m = None

        if self.anaconda.methodstr:
            m = self.anaconda.methodstr
        elif self.anaconda.stage2:
            m = self.anaconda.stage2

        if m:
            if m.startswith("cdrom:"):
                f.write("cdrom\n")
            elif m.startswith("hd:"):
                if m.count(":") == 3:
                    (part, fs, dir) = string.split(m[3:], ":")
                else:
                    (part, dir) = string.split(m[3:], ":")

                f.write("harddrive --partition=%s --dir=%s\n" % (part, dir))
            elif m.startswith("nfs:") or m.startswith("nfsiso:"):
                if m.count(":") == 3:
                    (method, opts, server, dir) = m.split(":")
                    f.write("nfs --server=%s --opts=%s --dir=%s\n" % (server, opts, dir))
                else:
                    (method, server, dir) = m.split(":")
                    f.write("nfs --server=%s --dir=%s\n" % (server, dir))
            elif m.startswith("ftp://") or m.startswith("http"):
                f.write("url --url=%s\n" % urllib.unquote(m))

        self.instLanguage.writeKS(f)
        if not self.isHeadless:
            self.keyboard.writeKS(f)
            self.network.writeKS(f)

        if self.rootPassword["isCrypted"]:
            args = " --iscrypted %s" % self.rootPassword["password"]
        else:
            args = " --iscrypted %s" % users.cryptPassword(self.rootPassword["password"], algo=self.getPassAlgo())

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
        self.storage.writeKS(f)

        if self.backend is not None:
            self.backend.writeKS(f)
            self.backend.writePackagesKS(f, self.anaconda)

        # Also write out any scripts from the input ksfile.
        if self.anaconda.isKickstart:
            for s in self.ksdata.scripts:
                f.write(s.__str__())

        # make it so only root can read, could have password
        os.chmod(filename, 0600)


    def __init__(self, anaconda, extraModules, displayMode, backend = None):
        self.displayMode = displayMode

        self.instLanguage = language.Language(self.displayMode)
        self.keyboard = keyboard.Keyboard()
        self.backend = backend
        self.anaconda = anaconda

        self.monitor = None
        self.videocard = None
        self.isHeadless = 0
        self.extraModules = extraModules

        self.simpleFilter = not iutil.isS390()

        self.reset()
