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
import iutil
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

    def writeKS(self, f, desktop=None):
        # FIXME: we really should have at least teh startxonboot and
        # defaultdesktop bits on s390
        if rhpl.getArch() == "s390":
            return
        
	if self.skipx:
	    f.write("skipx\n")
	    return

        args = self.getArgList(self.xserver.hwstate.get_resolution(),
			       self.xserver.hwstate.get_colordepth())
	if desktop: 
	    rl = desktop.getDefaultRunLevel() 
	    if rl and str(rl) == '5': 
		args = args + ['--startxonboot'] 
	    gui = desktop.getDefaultDesktop() 
	    if gui: 
		args = args + ['--defaultdesktop', string.lower(gui)] 

        f.write("xconfig %s\n" % string.join(args, " "))
        f.write("monitor %s\n" % string.join(self.getMonitorArgList(), " ")

    def getMonitorArgList(self):
        args = []
        monitor = self.xserver.monitorhw
        
        args = args + [ "--hsync", monitor.getMonitorHorizSync() ]
        args = args + [ "--vsync", monitor.getMonitorVertSync() ]

        return args

    def getArgList(self, res, depth):
        args = []
	vc = self.xserver.videohw

	args = args + [ "--driver", '"' + vc.primaryCard().getDriver() + '"' ]
	vram = vc.primaryCard().getVideoRam()
	if vram is not None:
	    args = args + [ "--videoram", vram]

        # XXX this isn't really quite right, but it works for the way
        # things are now
        args = args + [ "--resolution", res ]
        args = args + [ "--depth", str(depth) ]

        return args
