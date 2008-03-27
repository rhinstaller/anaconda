#
# xsetup.py - handles anaconda specific XFree86 needs
#
# Copyright (C) 2002, 2003  Red Hat, Inc.  All rights reserved.
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
# Author(s): Michael Fulbright <msf@redhat.com>
#

#
# should probably go in rhpl
#
import string
import rhpl
from rhpl.translate import _

class XSetup:
    def __init__(self, xserver, anaconda):
	self.skipx = 0
	self.xserver = xserver
        self.anaconda = anaconda

    def write(self, fn, keyboard):
        self.xserver.keyboard = keyboard
        self.xserver.generateConfig()

        if self.anaconda.isKickstart:
            res = self.anaconda.id.ksdata.xconfig.resolution

            if res:
                import xf86config
                screen = xf86config.getPrimaryScreen(self.xserver.config)
                screen.display[0].modes.insert(xf86config.XF86Mode(res))

        self.xserver.writeConfig(filename=fn+"/xorg.conf")

    def writeKS(self, f, desktop, ksconfig):
        if self.skipx:
            f.write("skipx\n")
            return

        # We don't want to write out the X config arguments unless they
        # were previously specified in kickstart.
        args = []
        if desktop:
	    rl = desktop.getDefaultRunLevel() 
	    if rl and str(rl) == '5': 
		args += ['--startxonboot'] 
	    gui = desktop.getDefaultDesktop() 
	    if gui: 
		args += ['--defaultdesktop', string.lower(gui)] 

        # We don't want anything else on s390.
        if rhpl.getArch() == "s390" and args != []:
            f.write("xconfig %s\n" % string.join(args, " "))
            return

        if ksconfig:
            s = ksconfig.xconfig.__str__().rstrip()
            f.write(s)

            for arg in args:
                if s.find(arg) == -1:
                    f.write(" %s" % arg)

            f.write("\n")
            f.write(ksconfig.monitor.__str__())
        elif args != []:
            f.write("xconfig %s\n" % string.join(args, " "))
