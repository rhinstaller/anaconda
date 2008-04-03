#
# desktop.py - install data for default desktop and run level
#
# Copyright (C) 2001, 2002  Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Author(s): Matt Wilson <msw@redhat.com>
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
            f = open(instPath + "/etc/sysconfig/init", "r")
        except IOError:
            log.warning ("there is no /etc/sysconfig/init, bad things will happen!")
            return

        lines = f.readlines()
        f.close()

        f = open(instPath + "/etc/sysconfig/init", "w")
        for line in lines:
            if line.startswith("GRAPHICAL="):
                if self.runlevel == 5:
                    line = "GRAPHICAL=yes\n"
                else:
                    line = "GRAPHICAL=no\n"

            f.write(line)

        f.close()

        if self.getDefaultDesktop():
            f = open(instPath + "/etc/sysconfig/desktop", "w")
            f.write(str (self))
            f.close()
