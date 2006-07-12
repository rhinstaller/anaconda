#
# firewall.py - firewall install data and installation
#
# Bill Nottingham <notting@redhat.com>
# Jeremy Katz <katzj@redhat.com>
#
# Copyright 2004 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import os
import iutil
import string
from flags import flags

from rhpl.translate import _, N_

import logging
log = logging.getLogger("anaconda")

class Firewall:
    def __init__ (self):
	self.enabled = 1
        self.trustdevs = []
	self.portlist = ["22:tcp"]

    def writeKS(self, f):
	f.write("firewall")

        if self.enabled:
	    for arg in self.getArgList():
		f.write(" " + arg)
	else:
	    f.write(" --disabled")

	f.write("\n")

    def getArgList(self):
	args = []

        if self.enabled:
            args.append("--enabled")
        else:
            args.append("--disabled")
            return args
        
        for dev in self.trustdevs:
            args = args + [ "--trust=%s" %(dev,) ]

	for port in self.portlist:
	    args = args + [ "--port=%s" %(port,) ]
                
	return args

    def write (self, instPath):
	args = [ "--quiet", "--nostart", "-f" ] + self.getArgList()

        try:
            if not flags.test:
                iutil.execWithRedirect("/usr/sbin/lokkit", args,
                                       root=instPath, stdout=None, stderr=None)
            else:
                log.error("would have run %s", args)
        except RuntimeError, msg:
            log.error ("lokkit run failed: %s", msg)
        except OSError, (errno, msg):
            log.error ("lokkit run failed: %s", msg)
        else:
            f = open(instPath +
                     '/etc/sysconfig/system-config-securitylevel', 'w')
            f.write("# system-config-securitylevel config written out by anaconda\n\n")
            for arg in args[3:]:
                f.write("%s\n" %(arg,))
            f.close()
