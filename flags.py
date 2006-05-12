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
	
    def __init__(self):
	self.__dict__['flags'] = {}
	self.__dict__['flags']['test'] = 0
	self.__dict__['flags']['rootpath'] = 0
	self.__dict__['flags']['expert'] = 0
	self.__dict__['flags']['serial'] = 0
	self.__dict__['flags']['setupFilesystems'] = 1
	self.__dict__['flags']['autostep'] = 0
	self.__dict__['flags']['autoscreenshot'] = 0
	self.__dict__['flags']['usevnc'] = 0
	self.__dict__['flags']['selinux'] = SELINUX_DEFAULT
        # for non-physical consoles like some ppc and sgi altix,
        # we need to preserve the console device and not try to
        # do things like bogl on them.  this preserves what that
        # device is
        self.__dict__['flags']['virtpconsole'] = None
        self.__dict__['flags']['runks'] = 0
        self.__dict__['flags']['display_mode'] = None

        # determine if selinux is enabled or not
        f = open("/proc/cmdline", "r")
        line = f.readline()
        f.close()

        tokens = line.split()
        for tok in tokens:
            if tok == "selinux":
                self.__dict__['flags']['selinux'] = 1
            elif tok == "selinux=0":
                self.__dict__['flags']['selinux'] = 0
            elif tok == "selinux=1":
                self.__dict__['flags']['selinux'] = 1

        if not os.path.exists("/selinux/load"):
            self.__dict__['flags']['selinux'] = 0

                
global flags
flags = Flags()
