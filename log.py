import sys

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
                self.logFile = sys.stderr
	elif file:
	    self.logFile = file
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
