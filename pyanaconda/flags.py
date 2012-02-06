#
# flags.py: global anaconda flags
#
# Copyright (C) 2001  Red Hat, Inc.  All rights reserved.
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

import os
import selinux
import shlex
from constants import *

# A lot of effort, but it only allows a limited set of flags to be referenced
class Flags(object):
    def __setattr__(self, attr, val):
        if attr not in self.__dict__ and not self._in_init:
            raise AttributeError, attr
        else:
            self.__dict__[attr] = val

    def get(self, attr, val=None):
        return getattr(self, attr, val)

    def createCmdlineDict(self):
        cmdlineDict = {}
        cmdline = open("/proc/cmdline", "r").read().strip()

        # if the BOOT_IMAGE contains a space, pxelinux will strip one of the
        # quotes leaving one at the end that shlex doesn't know what to do
        # with
        (left, middle, right) = cmdline.rpartition("BOOT_IMAGE=")
        if right.count('"') % 2:
            cmdline = left + middle + '"' + right

        lst = shlex.split(cmdline)

        for i in lst:
            try:
                (key, val) = i.split("=", 1)
            except:
                key = i
                val = None

            cmdlineDict[key] = val

        return cmdlineDict


    def decideCmdlineFlag(self, flag):
        if self.cmdline.has_key(flag) \
                and not self.cmdline.has_key("no" + flag) \
                and self.cmdline[flag] != "0":
            setattr(self, flag, 1)

    def __init__(self):
        self.__dict__['_in_init'] = True
        self.test = 0
        self.livecdInstall = 0
        self.dlabel = 0
        self.ibft = 1
        self.iscsi = 0
        self.serial = 0
        self.autostep = 0
        self.autoscreenshot = 0
        self.usevnc = 0
        self.vncquestion = True
        self.mpath = 1
        self.dmraid = 1
        self.selinux = SELINUX_DEFAULT
        self.debug = 0
        self.targetarch = None
        self.cmdline = self.createCmdlineDict()
        self.useIPv4 = True
        self.useIPv6 = True
        self.sshd = 0
        self.preexisting_x11 = False
        self.noverifyssl = False
        self.imageInstall = False
        # for non-physical consoles like some ppc and sgi altix,
        # we need to preserve the console device and not try to
        # do things like bogl on them.  this preserves what that
        # device is
        self.virtpconsole = None
        self.nogpt = False
        # Lock it down: no more creating new flags!
        self.__dict__['_in_init'] = False

        if 'selinux' in self.cmdline:
            if self.cmdline['selinux'] not in ("0", "off", "no"):
                self.selinux = 1
            else:
                self.selinux = 0

        self.decideCmdlineFlag('sshd')

        if self.cmdline.has_key("debug"):
            self.debug = self.cmdline['debug']

        if self.cmdline.has_key("rpmarch"):
            self.targetarch = self.cmdline['rpmarch']

        if not selinux.is_selinux_enabled():
            self.selinux = 0

        self.nogpt = self.cmdline.has_key("nogpt")

global flags
flags = Flags()

