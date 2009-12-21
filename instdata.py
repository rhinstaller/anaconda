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

        self.network = network.Network()
        self.firewall = firewall.Firewall()
        self.security = security.Security()
        self.timezone = timezone.Timezone()
        self.timezone.setTimezoneInfo(self.instLanguage.getDefaultTimeZone(self.anaconda.rootPath))
        self.users = None
        self.rootPassword = { "isCrypted": False, "password": "", "lock": False }
        self.auth = "--enableshadow --passalgo=sha512 --enablefingerprint"
        self.desktop = desktop.Desktop()
        self.storage = storage.Storage(self.anaconda)
        self.bootloader = booty.getBootloader(self)
        self.escrowCertificates = {}

        if iutil.isS390() or self.anaconda.ksdata:
            self.firstboot = FIRSTBOOT_SKIP
        else:
            self.firstboot = FIRSTBOOT_DEFAULT

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

        if not self.anaconda.isHeadless:
            self.keyboard.write (self.anaconda.rootPath)

        self.timezone.write (self.anaconda.rootPath)

        args = ["--update", "--nostart"] + shlex.split(self.auth)

        try:
            iutil.execWithRedirect("/usr/sbin/authconfig", args,
                                   stdout = "/dev/tty5", stderr = "/dev/tty5",
                                   root = self.anaconda.rootPath)
        except RuntimeError, msg:
                log.error("Error running %s: %s", args, msg)

        self.network.write (instPath=self.anaconda.rootPath,
                            anaconda=self.anaconda)
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

        if self.anaconda.ksdata:
            for gd in self.anaconda.ksdata.group.groupList:
                if not self.users.createGroup(name=gd.name,
                                              gid=gd.gid,
                                              root=self.anaconda.rootPath):
                    log.error("Group %s already exists, not creating." % gd.name)

            for ud in self.anaconda.ksdata.user.userList:
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

    def writeKS(self, f):
        self.instLanguage.writeKS(f)
        if not self.anaconda.isHeadless:
            self.keyboard.writeKS(f)
            self.network.writeKS(f)

        if self.rootPassword["isCrypted"]:
            args = " --iscrypted %s" % self.rootPassword["password"]
        else:
            args = " --iscrypted %s" % users.cryptPassword(self.rootPassword["password"], algo=self.getPassAlgo())

        if self.rootPassword["lock"]:
            args += " --lock"

        f.write("rootpw %s\n" % args)

        self.firewall.writeKS(f)
        if self.auth.strip() != "":
            f.write("authconfig %s\n" % self.auth)
        self.security.writeKS(f)
        self.timezone.writeKS(f)
        self.bootloader.writeKS(f)
        self.storage.writeKS(f)

    def __init__(self, anaconda, extraModules):
        self.instLanguage = language.Language(anaconda.displayMode)
        self.keyboard = keyboard.Keyboard()
        self.anaconda = anaconda
        self.extraModules = extraModules
        self.simpleFilter = True

        self.reset()
