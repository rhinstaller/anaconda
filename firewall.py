#
# firewall.py - firewall install data and installation
#
# Copyright (C) 2004  Red Hat, Inc.  All rights reserved.
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
# Author(s): Bill Nottingham <notting@redhat.com>
#            Jeremy Katz <katzj@redhat.com>
#

import iutil
import os.path
from flags import flags
from constants import *

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("anaconda")

class Firewall:
    def __init__ (self):
	self.enabled = 1
        self.trustdevs = []
	self.portlist = []
        self.servicelist = []

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

        if not self.enabled:
            args.append("--disabled")
            return args

        if not "ssh" in self.servicelist and not "22:tcp" in self.portlist:
            args += ["--service=ssh"]

        for dev in self.trustdevs:
            args = args + [ "--trust=%s" %(dev,) ]

	for port in self.portlist:
	    args = args + [ "--port=%s" %(port,) ]

        for service in self.servicelist:
            args = args + [ "--service=%s" % (service,) ]

	return args

    def write (self, instPath):
	args = [ "--quiet", "--nostart", "-f" ] + self.getArgList()

        try:
            if not os.path.exists("%s/etc/sysconfig/iptables" %(instPath,)):
                iutil.execWithRedirect("/usr/sbin/lokkit", args,
                                       root=instPath, stdout="/dev/null",
                                       stderr="/dev/null")
            else:
                log.error("would have run %s", args)
        except RuntimeError, msg:
            log.error ("lokkit run failed: %s", msg)
        except OSError as e:
            log.error ("lokkit run failed: %s", e.strerror)
        else:
            f = open(instPath +
                     '/etc/sysconfig/system-config-firewall', 'w')
            f.write("# system-config-firewall config written out by anaconda\n\n")
            for arg in args[3:]:
                f.write("%s\n" %(arg,))
            f.close()
