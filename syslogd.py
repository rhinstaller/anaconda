#
# syslogd.py - a simple syslogd implementation and wrapper for launching it
#
# Copyright (C) 1999, 2000, 2001  Red Hat, Inc.  All rights reserved.
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
#

import sys, os
import string
from socket import *
from select import select

import logging
log = logging.getLogger("anaconda")

class Syslogd:
    def goSyslog(self, output, sockName):
	sock = socket(AF_UNIX, SOCK_STREAM)

	try:
	    os.unlink(sockName)
	except os.error:
	    pass

	sock.bind(sockName)
	acceptedFds = []
	sock.listen(5)

	while (1):
	    list = acceptedFds + [ sock ]
	    list = select(list, [], [])[0]
	    try:
		list.remove(sock)
		(fd, remoteAddr) = sock.accept()
		acceptedFds.append(fd)
	    except ValueError:
		pass

	    for fd in list:
		msg = fd.recv(50)
                msg = string.replace(msg, chr(0), "\n")
		if (msg):
		    output.write(msg)
                    output.flush()
		else:
		    acceptedFds.remove(fd)
		    fd.close()

    def __init__(self, root = "", output = sys.stdout, socket = "/dev/log"):
	filename = root + socket
        self.goSyslog(output, filename)

class InstSyslog:
    def __init__ (self):
        self.pid = -1

    def start (self, root, log):
        # don't run in the "install from livecd" case
        if not os.path.exists("/usr/bin/syslogd"): 
            return
        self.pid = os.fork ()
        if not self.pid:
            # look on PYTHONPATH first, so we use updated anaconda
            path = "/usr/bin/syslogd"
            if os.environ.has_key('PYTHONPATH'):
                for f in string.split(os.environ['PYTHONPATH'], ":"):
                    if os.access (f+"/syslogd", os.X_OK):
                        path = f+"/syslogd"
                        break

            if os.path.exists(path):
                os.execv (path, ("syslogd", root, log))

    def stop(self):
        if self.pid == -1:
            log.warn("syslogd not running to kill!")
            return
        try:
            os.kill (self.pid, 15)
        except OSError as e:
            log.error("killing syslogd failed: %s %s" %(e.errno, e.strerror))
	
        try:
	    os.waitpid (self.pid, 0)
        except OSError as e:
            log.error("exception from waitpid in syslogd::stop: %s %s" % (e.errno, e.strerror))

        self.pid = -1

syslog = InstSyslog()
