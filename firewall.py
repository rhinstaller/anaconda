#
# firewall.py - firewall install data and installation
#
# Bill Nottingham <notting@redhat.com>
#
# Copyright 2003 Red Hat, Inc.
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

from rhpl.log import log

class Firewall:
    def __init__ (self):
	self.enabled = 1
	self.ssh = 0
	self.telnet = 0
	self.smtp = 0
	self.http = 0
	self.ftp = 0
	self.portlist = ""
	self.ports = []
	self.trustdevs = []

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
            args.append ("--enabled")
        else:
            args.append("--disabled")
            return args
        
	if self.portlist:
	    ports = string.split(self.portlist,',')
	    for port in ports:
		port = string.strip(port)
                try:
                    if not string.index(port,':'):
                        port = '%s:tcp' % port
                except:
                    pass
		self.ports.append(port)
	for port in self.ports:
	    args = args + [ "--port=%s" %(port,) ]
	if self.smtp:
	    args = args + [ "--port=smtp:tcp" ]
	if self.http:
	    args = args + [ "--port=http:tcp" ]
	if self.ftp:
	    args = args + [ "--port=ftp:tcp" ]
	if self.ssh:
	    args = args + [ "--port=ssh:tcp" ]
	if self.telnet:
	    args = args + [ "--port=telnet:tcp" ]
	for dev in self.trustdevs:
	    args = args + [ "--trust=%s" %(dev,) ]

	return args

    def write (self, instPath):
	args = [ "/usr/sbin/lokkit", "--quiet", "--nostart" ]

        if self.enabled:
	    args = args + self.getArgList()

            try:
                if flags.setupFilesystems:
                    iutil.execWithRedirect(args[0], args, root = instPath,
                                           stdout = None, stderr = None)
                else:
                    log("would have run %s", args)
            except RuntimeError, msg:
                log ("lokkit run failed: %s", msg)
            except OSError, (errno, msg):
                log ("lokkit run failed: %s", msg)
            else:
                f = open(instPath +
                         '/etc/sysconfig/system-config-securitylevel', 'w')
                f.write("# system-config-securitylevel config written out by anaconda\n\n")
                for arg in args[3:]:
                    f.write("%s\n" %(arg,))
                f.close()
                    
        else:
            # remove /etc/sysconfig/iptables
	    file = instPath + "/etc/sysconfig/iptables"
	    if os.access(file, os.O_RDONLY):
                os.remove(file)

