#
# log.py - persistent debugging log service
#
# Matt Wilson <msw@redhat.com>
#
# Copyright 2000-2001 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import sys

class LogFile:
    def __init__ (self):
        self.logFile = None
        self.logFile2 = None
    
    def close (self):
        try:
            self.logFile.close ()
            self.logFile2.close()
        except:
            pass
    
    def open (self, file):
	if type(file) == type("hello"):
            try:
                self.logFile = open(file, "w")
            except:
                self.logFile = sys.stderr
	elif file:
	    self.logFile = file
	else:
            self.logFile = open("/dev/tty3", "w")
            try:
                self.logFile2 = open("/tmp/anaconda.log", "a")
            except:
                pass

    def __call__ (self, format, *args):
        if not self.logFile:
            raise RuntimeError, "log file not open yet"
        
        if args:
            self.logFile.write ("* %s\n" % (format % args))
        else:
            self.logFile.write ("* %s\n" % format)

        if self.logFile2:
            if args:
                self.logFile2.write ("* %s\n" % (format % args))
            else:
                self.logFile2.write ("* %s\n" % format)
            self.logFile2.flush()

    def getFile (self):
        return self.logFile.fileno ()
            
log = LogFile()
