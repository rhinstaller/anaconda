#
# xsetup.py - handles anaconda specific XFree86 needs
#
# Michael Fulbright <msf@redhat.com>
#
# Copyright 2002 Red Hat, Inc.
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
import rhpl.xserver as xserver

import string
class XSetup:

    def __init__(self, hwstate):
	self.skipx = 0
	self.imposed_sane_default = 0
	self.xhwstate = hwstate

    #
    # mouse and keyboard maybe should be part of this object
    #
    # really all of this should be in rhpl probably
    #
    def write(self, fn, mouse, keyboard):
	#
	# always turn dri on
	#
	self.xhwstate.set_dri_enabled(1)
	
	outfile = fn + "/XF86Config"
	xserver.writeXConfig(outfile, self.xhwstate, mouse, keyboard,
			     standalone = 0)	

    def writeKS(self, f, desktop=None):
	if self.skipx:
	    f.write("skipx\n")
	    return

        args = self.getArgList(self.xhwstate.get_resolution(),
			       self.xhwstate.get_colordepth())
	if desktop: 
	    rl = desktop.getDefaultRunLevel() 
	    if rl and str(rl) == '5': 
		args = args + ['--startxonboot', ''] 
	    gui = desktop.getDefaultDesktop() 
	    if gui: 
		args = args + ['--defaultdesktop', string.lower(gui)] 

	f.write("xconfig")
	for arg in args: 
	    f.write(" " + arg)
	f.write("\n")

    def getArgList(self, res, depth):
        args = []
        monitor = self.xhwstate.monitor
	vc = self.xhwstate.videocard

        args = args + [ "--card", '"' + vc.primaryCard().shortDescription() + '"' ]
        args = args + [ "--videoram", vc.primaryCard().getVideoRam() ]
        args = args + [ "--hsync", monitor.getMonitorHorizSync() ]
        args = args + [ "--vsync", monitor.getMonitorVertSync() ]

        # XXX this isn't really quite right, but it works for the way
        # things are now
        args = args + [ "--resolution", res ]
        args = args + [ "--depth", str(depth) ]

        return args

    

