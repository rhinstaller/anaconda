import string
import kudzu
import iutil
import isys
from log import log

class Desktop:
#
# This class represents the default desktop to run and the default runlevel
# to start in
#

    def setDefaultDesktop(self, desktop):
        self.desktop = desktop

    def setDefaultRunLevel(self, runlevel):
        if str(runlevel) != "3" and str(runlevel) != "5":
            raise RuntimeError, "Desktop::setDefaultRunLevel() - Must specify runlevel as 3 or 5!"
        self.runlevel = runlevel

    def getDefaultDesktop(self):
        return self.desktop

    def getDefaultRunLevel(self):
        return self.runlevel

    def __init__ (self):
        self.desktop = None
        self.runlevel = 3

    def write (self, instPath):
	#
	# XXX
	#
	return

        try:
            inittab = open (instPath + '/etc/inittab', 'r')
        except IOError:
            log ("WARNING, there is no inittab, bad things will happen!")
            return
        lines = inittab.readlines ()
        inittab.close ()
        inittab = open (instPath + '/etc/inittab', 'w')        
        for line in lines:
            if len (line) > 3 and line[:3] == "id:":
                fields = string.split (line, ':')
                fields[1] = str (self.runlevel)
                line = string.join (fields, ':')
            inittab.write (line)
        inittab.close ()
