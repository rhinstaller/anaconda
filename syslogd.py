#
# syslogd.py - a simple syslogd implementation and wrapper for launching it
#
# Erik Troan <ewt@redhat.com>
#
# Copyright 1999-2001 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
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
	output = output
	filename = root + socket;
        self.goSyslog(output, filename)

class InstSyslog:
    def __init__ (self):
        self.pid = -1;

    def start (self, root, log):
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
            raise RuntimeError, "syslogd not running"
        try:
            os.kill (self.pid, 15)
        except OSError, (num, msg):
            log.error("killing syslogd failed: %s %s" %(num, msg))
	
        try:
	    os.waitpid (self.pid, 0)
        except OSError, (num, msg):
            log.error("exception from waitpid in syslogd::stop: %s %s" % (num, msg))

        self.pid = -1

syslog = InstSyslog()
