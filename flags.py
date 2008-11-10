#
# flags.py: global anaconda flags
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

import os
import shlex
from constants import *

# A lot of effort, but it only allows a limited set of flags to be referenced
class Flags:

    def __getattr__(self, attr):
	if self.__dict__['flags'].has_key(attr):
	    return self.__dict__['flags'][attr]

	raise AttributeError, attr

    def __setattr__(self, attr, val):
	if self.__dict__['flags'].has_key(attr):
	    self.__dict__['flags'][attr] = val
	else:
	    raise AttributeError, attr

    def createCmdlineDict(self):
        cmdlineDict = {}
        cmdline = open("/proc/cmdline", "r").read().strip()

        # if the BOOT_IMAGE contains a space, pxelinux will strip one of the
        # quotes leaving one at the end that shlex doesn't know what to do
        # with
        if cmdline.find("BOOT_IMAGE=") and cmdline.endswith('"'):
            cmdline = cmdline.replace("BOOT_IMAGE=", "BOOT_IMAGE=\"")

        lst = shlex.split(cmdline)

        for i in lst:
            try:
                (key, val) = i.split("=", 1)
            except:
                key = i
                val = True

            cmdlineDict[key] = val

        return cmdlineDict
	
    def __init__(self):
	self.__dict__['flags'] = {}
	self.__dict__['flags']['test'] = 0
	self.__dict__['flags']['rootpath'] = 0
	self.__dict__['flags']['livecd'] = 0        
	self.__dict__['flags']['expert'] = 0
	self.__dict__['flags']['dlabel'] = 0
	self.__dict__['flags']['ibft'] = 1
	self.__dict__['flags']['iscsi'] = 0
	self.__dict__['flags']['serial'] = 0
	self.__dict__['flags']['setupFilesystems'] = 1
	self.__dict__['flags']['autostep'] = 0
	self.__dict__['flags']['autoscreenshot'] = 0
	self.__dict__['flags']['usevnc'] = 0
	self.__dict__['flags']['vncquestion'] = True
        self.__dict__['flags']['mpath'] = 0
	self.__dict__['flags']['dmraid'] = 1
	self.__dict__['flags']['selinux'] = SELINUX_DEFAULT
        self.__dict__['flags']['debug'] = 0
	self.__dict__['flags']['targetarch'] = None
        self.__dict__['flags']['cmdline'] = self.createCmdlineDict()
        self.__dict__['flags']['useIPv4'] = True
        self.__dict__['flags']['useIPv6'] = True
        # for non-physical consoles like some ppc and sgi altix,
        # we need to preserve the console device and not try to
        # do things like bogl on them.  this preserves what that
        # device is
        self.__dict__['flags']['virtpconsole'] = None

        if self.__dict__['flags']['cmdline'].has_key("selinux"):
            if self.__dict__['flags']['cmdline']["selinux"]:
                self.__dict__['flags']['selinux'] = 1
            else:
                self.__dict__['flags']['selinux'] = 0

        if self.__dict__['flags']['cmdline'].has_key("debug"):
            self.__dict__['flags']['debug'] = self.__dict__['flags']['cmdline']['debug']

        if self.__dict__['flags']['cmdline'].has_key("rpmarch"):
            self.__dict__['flags']['targetarch'] = self.__dict__['flags']['cmdline']['rpmarch']             

        if not os.path.exists("/selinux/load"):
            self.__dict__['flags']['selinux'] = 0

                
global flags
flags = Flags()
