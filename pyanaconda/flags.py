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

import selinux
import shlex
import glob
from pyanaconda.constants import SELINUX_DEFAULT
from collections import OrderedDict

import logging
log = logging.getLogger("anaconda")

# A lot of effort, but it only allows a limited set of flags to be referenced
class Flags(object):
    def __setattr__(self, attr, val):
        # pylint: disable-msg=E1101
        if attr not in self.__dict__ and not self._in_init:
            raise AttributeError(attr)
        else:
            self.__dict__[attr] = val

    def get(self, attr, val=None):
        return getattr(self, attr, val)

    def set_cmdline_bool(self, flag):
        if flag in self.cmdline:
            setattr(self, flag, self.cmdline.getbool(flag))

    def __init__(self, read_cmdline=True):
        self.__dict__['_in_init'] = True
        self.livecdInstall = 0
        self.dlabel = 0
        self.ibft = 1
        self.iscsi = 0
        self.usevnc = 0
        self.vncquestion = True
        self.mpath = 1
        self.dmraid = 1
        self.selinux = SELINUX_DEFAULT
        self.debug = 0
        self.targetarch = None
        self.useIPv4 = True
        self.useIPv6 = True
        self.armPlatform = None
        self.preexisting_x11 = False
        self.noverifyssl = False
        self.imageInstall = False
        self.automatedInstall = False
        self.dirInstall = False
        self.askmethod = False
        self.eject = True
        self.extlinux = False
        self.gpt = False
        self.leavebootorder = False
        self.testing = False
        self.dnf = False
        self.mpathFriendlyNames = True
        # ksprompt is whether or not to prompt for missing ksdata
        self.ksprompt = True
        # parse the boot commandline
        self.cmdline = BootArgs()
        # Lock it down: no more creating new flags!
        self.__dict__['_in_init'] = False
        if read_cmdline:
            self.read_cmdline()

    def read_cmdline(self):
        for f in ("selinux", "debug", "leavebootorder", "testing"):
            self.set_cmdline_bool(f)

        if "rpmarch" in self.cmdline:
            self.targetarch = self.cmdline.get("rpmarch")

        if not selinux.is_selinux_enabled():
            self.selinux = 0

        if "extlinux" in self.cmdline:
            self.extlinux = True

        if "gpt" in self.cmdline:
            self.gpt = True

        if "dnf" in self.cmdline:
            self.dnf = True

cmdline_files = ['/proc/cmdline', '/run/install/cmdline',
                 '/run/install/cmdline.d/*.conf', '/etc/cmdline']
class BootArgs(OrderedDict):
    """
    Hold boot arguments as an OrderedDict.
    """
    def __init__(self, cmdline=None, files=None):
        """
        Create a BootArgs object.
        Reads each of the "files", then parses "cmdline" if it was provided.
        """
        OrderedDict.__init__(self)
        if files is None:
            self.read(cmdline_files)
        elif files:
            self.read(files)
        if cmdline:
            self.readstr(cmdline)

    def read(self, filenames):
        """
        Read and parse a filename (or a list of filenames).
        Files that can't be read are silently ignored.
        Returns a list of successfully read files.
        filenames can contain *, ?, and character ranges expressed with []
        """
        readfiles = []
        if type(filenames) == str:
            filenames = [filenames]

        # Expand any filename globs
        filenames = [f for g in filenames for f in glob.glob(g)]

        for f in filenames:
            try:
                self.readstr(open(f).read())
                readfiles.append(f)
            except IOError:
                continue
        return readfiles

    def readstr(self, cmdline):
        cmdline = cmdline.strip()
        # if the BOOT_IMAGE contains a space, pxelinux will strip one of the
        # quotes leaving one at the end that shlex doesn't know what to do
        # with
        (left, middle, right) = cmdline.rpartition("BOOT_IMAGE=")
        if right.count('"') % 2:
            cmdline = left + middle + '"' + right

        # shlex doesn't properly handle \\ (it removes them)
        # which scrambles the spaces used in labels so use underscores
        cmdline = cmdline.replace("\\x20", "_")

        lst = shlex.split(cmdline)

        for i in lst:
            if "=" in i:
                (key, val) = i.split("=", 1)
            else:
                key = i
                val = None

            self[key] = val

    def getbool(self, arg, default=False):
        """
        Return the value of the given arg, as a boolean. The rules are:
        - "arg", "arg=val": True
        - "noarg", "noarg=val", "arg=[0|off|no]": False
        """
        result = default
        for a in self:
            if a == arg:
                if self[arg] in ("0", "off", "no"):
                    result = False
                else:
                    result = True
            elif a == 'no'+arg:
                result = False # XXX: should noarg=off -> True?
        return result

def can_touch_runtime_system(msg, touch_live=False):
    """
    Guard that should be used before doing actions that modify runtime system.

    :param msg: message to be logged in case that runtime system cannot be touched
    :type msg: str
    :param touch_live: whether to allow touching liveCD installation system
    :type touch_live: bool
    :rtype: bool

    """

    if flags.livecdInstall and not touch_live:
        log.info("Not doing '%s' in live installation", msg)
        return False

    if flags.imageInstall:
        log.info("Not doing '%s' in image installation", msg)
        return False

    if flags.dirInstall:
        log.info("Not doing '%s' in directory installation", msg)
        return False

    if flags.testing:
        log.info("Not doing '%s', because we are just testing", msg)
        return False

    return True

global flags
flags = Flags()

