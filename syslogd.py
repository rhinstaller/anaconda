# Simple syslog

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

    def __del__(self):
	self.kill()

    def kill(self):
	os.kill(self.child, 15)
        try:
            os.waitpid(self.child, 0)
        except OSError (errno, msg):
            print __name__, "waitpid:", msg

    def __init__(self, root = "", output = sys.stdout, socket = "/dev/log"):
	output = output
	filename = root + socket;
        self.goSyslog(output, filename)
