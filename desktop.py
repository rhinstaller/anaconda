#
# desktop.py - install data for default desktop and run level
#
# Matt Wilson <msw@redhat.com>
#
# Copyright 2001-2002 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import string

from rhpl.simpleconfig import SimpleConfigFile

import logging
log = logging.getLogger("anaconda")

class Desktop (SimpleConfigFile):
#
# This class represents the default desktop to run and the default runlevel
# to start in
#
    def setDefaultRunLevel(self, runlevel):
        if str(runlevel) != "3" and str(runlevel) != "5":
            raise RuntimeError, "Desktop::setDefaultRunLevel() - Must specify runlevel as 3 or 5!"
        self.runlevel = runlevel

    def getDefaultRunLevel(self):
        return self.runlevel

    def setDefaultDesktop(self, desktop):
        self.info["DESKTOP"] = desktop

    def getDefaultDesktop(self):
        return self.get("DESKTOP")

    def __init__ (self):
        SimpleConfigFile.__init__ (self)
        self.runlevel = 3

    def write (self, instPath):
        try:
            inittab = open (instPath + '/etc/inittab', 'r')
        except IOError:
            log.warning ("there is no inittab, bad things will happen!")
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

	f = open(instPath + "/etc/sysconfig/desktop", "w")
	f.write(str (self))
	f.close()
