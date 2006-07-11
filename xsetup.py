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
import rhpl
import rhpxl.xserver as xserver
from rhpl.translate import _


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
        # always turn dri on FIXME: except on ia64
        if rhpl.getArch() == "ia64":
            self.xhwstate.set_dri_enabled(0)
        else:
            self.xhwstate.set_dri_enabled(1)

	#
	# XXX - cleanup monitor name to not include 'DDC Probed Monitor'
	#       in its string if its there.
	#
	#       This is around for legacy reasons.  The monitor description
	#       string passed around inside anaconda includes this prefix
	#       so that the UI can properly display the monitor as a DDC
	#       probed value versus a user selected value.
	#
	monname = self.xhwstate.get_monitor_name()
	if monname is not None:
	    ddc_monitor_string = _("DDC Probed Monitor")
	    if monname[:len(ddc_monitor_string)] == ddc_monitor_string:
		self.xhwstate.set_monitor_name(monname[len(ddc_monitor_string)+3:])
		
	outfile = fn + "/xorg.conf"
	xserver.writeXConfig(outfile, self.xhwstate, mouse, keyboard)

	# restore monitor name
	self.xhwstate.set_monitor_name(monname)

    def writeKS(self, f, desktop=None):
        # FIXME: we really should have at least teh startxonboot and
        # defaultdesktop bits on s390
        if rhpl.getArch() == "s390":
            return
        
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

        f.write("monitor")
        for arg in self.getMonitorArgList():
            f.write(" " + arg)
        f.write("\n")

    def getMonitorArgList(self):
        args = []
        monitor = self.xhwstate.monitor
        
        args = args + [ "--hsync", monitor.getMonitorHorizSync() ]
        args = args + [ "--vsync", monitor.getMonitorVertSync() ]

        return args

    def getArgList(self, res, depth):
        args = []
	vc = self.xhwstate.videocard

	args = args + [ "--driver", '"' + vc.primaryCard().getDriver() + '"' ]
	vram = vc.primaryCard().getVideoRam()
	if vram is not None:
	    args = args + [ "--videoram", vram]

        # XXX this isn't really quite right, but it works for the way
        # things are now
        args = args + [ "--resolution", res ]
        args = args + [ "--depth", str(depth) ]

        return args
