#
# log.py - persistent debugging log service
#
# Matt Wilson <msw@redhat.com>
# Michael Fulbright <msf@redhat.com>
#
# Copyright 2000-2002 Red Hat, Inc.
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

class Anaconda_LogFile:
    def __init__ (self):
        self.logFile = None
        self.logFile2 = None
        self.failcount = 0

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
            if iutil.getArch() != "s390":
                self.logFile = open("/dev/tty3", "w")
            else:
                # we don't really want to have to write this stuff to two
                # files.  
                self.logFile = None
            try:
                self.logFile2 = open("/tmp/anaconda.log", "a")
            except:
                self.logFile2 = None

    def __call__ (self, format, *args):
        if not self.logFile and not self.logFile2:
            raise RuntimeError, "log file not open yet"

        for file in [self.logFile, self.logFile2]:
            if file is None:
                continue
            if args:
                file.write ("* %s\n" % (format % args))
            else:
                file.write ("* %s\n" % format)

            try:
                file.flush()
            except IOError:
                # if we can't write here, there's not much we can do.
                # keep a counter of the number of times it's failed
                # if we fail more than 10 times, just abort writing to
                # the logfile
                self.failcount = self.failcount + 1
                if self.failcount > 10:
                    file = None

    def getFile (self):
        return self.logFile.fileno ()
            
anaconda_log = Anaconda_LogFile()
