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

class XSetup:

    def __init__(self, hwstate):
	self.skipx = 0
	self.xhwstate = hwstate

    #
    # mouse and keyboard maybe should be part of this object
    #
    # really all of this should be in rhpl probably
    #
    def write(self, fn, mouse, keyboard):
	outfile = fn + "/XF86Config"
	xserver.writeXConfig(outfile, self.xhwstate, mouse, keyboard,
			     standalone = 0)	

    def writeKS(self, f, desktop=None):
	return
    
	#
	# this needs lots of work
	#
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
        vc = self.videocard

        args = args + [ "--card", '"' + vc.shortDescription() + '"' ]
        args = args + [ "--videoram", vc.getVideoRam() ]
        args = args + [ "--hsync", self.monitor.getMonitorHorizSync() ]
        args = args + [ "--vsync", self.monitor.getMonitorVertSync() ]

        # XXX this isn't really quite right, but it works for the way
        # things are now
        args = args + [ "--resolution", res ]
        args = args + [ "--depth", depth ]

        return args

    

