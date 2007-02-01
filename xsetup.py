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
    def __init__(self, xserver, anaconda):
	self.skipx = 0
	self.xserver = xserver
        self.anaconda = anaconda

    def write(self, fn, mouse, keyboard):
        self.xserver.keyboard = keyboard
        self.xserver.mousehw = mouse
        self.xserver.generateConfig()

        res = self.anaconda.id.ksdata.xconfig.resolution

        if self.anaconda.isKickstart and res:
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
