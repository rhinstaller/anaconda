#
# xsetup.py - handles anaconda specific XFree86 needs
#
# Michael Fulbright <msf@redhat.com>
#
# Copyright 2002,2003 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

#
# should probably go in rhpl
#
import string
import rhpl
from rhpl.translate import _

class XSetup:
    def __init__(self, xserver):
	self.skipx = 0
	self.imposed_sane_default = 0
	self.xserver = xserver

    def write(self, fn, mouse, keyboard):
        self.xserver.keyboard = keyboard
        self.xserver.mousehw = mouse
        self.xserver.generateConfig()
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

        if ksconfig:
            if ksconfig.xconfig["driver"] != "":
                args += [ "--driver", ksconfig.xconfig["driver"] ]
            if ksconfig.xconfig["videoRam"] != "":
                args += [ "--videoram", ksconfig.xconfig["videoRam"] ]
            if ksconfig.xconfig["resolution"] != "":
                args += [ "--resolution", ksconfig.xconfig["resolution"] ]
            if ksconfig.xconfig["depth"] != 0:
                args += [ "--depth", str(ksconfig.xconfig["depth"]) ]

        if args != []:
            f.write("xconfig %s\n" % string.join(args, " "))

        args = []
        if ksconfig:
            if ksconfig.monitor["monitor"] != "":
                args += [ "--monitor", ksconfig.monitor["monitor"] ]
            if ksconfig.monitor["hsync"] != "":
                args += [ "--hsync", ksconfig.monitor["hsync"] ]
            if ksconfig.monitor["vsync"] != "":
                args += [ "--vsync", ksconfig.monitor["vsync"] ]

        if args != []:
            f.write("monitor %s\n" % string.join(args, " "))
