import sys, os

class LogFile:
    def __init__ (self):
        self.logFile = None
    
    def close (self):
        self.logFile.close ()
    
    def open (self, serial, reconfigOnly, test, setupFilesystems):
	if reconfigOnly:
	    self.logFile = open("/tmp/reconfig.log", "w")
        elif not setupFilesystems:
            self.logFile = sys.stderr
        elif serial:
	    self.logFile = open("/tmp/install.log", "w")
	elif test:
	    self.logFile = open("/tmp/anaconda-debug.log", "w")
	else:
	    self.logFile = open("/dev/tty3", "w")

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
