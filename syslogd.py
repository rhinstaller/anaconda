#
# syslogd.py - a simple syslogd implementation
#
# Erik Troan <ewt@redhat.com>
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

import sys, os
from socket import *
from select import select

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
		if (msg):
		    output.write(msg)
		else:
		    acceptedFds.remove(fd)
		    fd.close()

    def __init__(self, root = "", output = sys.stdout, socket = "/dev/log"):
	output = output
	filename = root + socket;
        self.goSyslog(output, filename)
