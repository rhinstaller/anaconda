#
# log.py - persistent debugging log service
#
# Matt Wilson <msw@redhat.com>
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

import sys
import iutil

class LogFile:
    def __init__ (self):
        self.logFile = None
    
    def close (self):
        self.logFile.close ()
    
    def open (self, file):
	if type(file) == type("hello"):
            try:
                self.logFile = open(file, "w")
            except:
		if iutil.getArch() != "s390" and iutil.getArch() != "s390x":
		    self.logFile = sys.stderr
		else:
		    self.logFile = open("/anaconda-s390.log", "w")
	elif file:
	    self.logFile = file
	else:
	    if iutil.getArch() != "s390" and iutil.getArch() != "s390x":
		self.logFile = open("/dev/tty3", "w")
	    else:
		self.logFile = open("/anaconda-s390.log", "w")

    def __call__ (self, format, *args):
        if not self.logFile:
            raise RuntimeError, "log file not open yet"
        
        if args:
            self.logFile.write ("* %s\n" % (format % args))
        else:
            self.logFile.write ("* %s\n" % format)

    def getFile (self):
        return self.logFile.fileno ()
            
log = LogFile()
