from gtk import *
from iw import *
from gui import _

import string
import sys
import iutil

"""
_("Video Card")
_("Monitor")
_("Video Ram")
_("Horizontal Frequency Range")
_("Vertical Frequency Range")
_("Test failed")
"""

class XCustomWindow (InstallWindow):
    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        self.todo = ics.getToDo ()
        ics.setTitle (_("Customize X Configuration"))
        ics.setHTML ("<HTML><BODY>This is the configuration customization screen<</BODY></HTML>")
        self.ics.setNextEnabled (TRUE)
        
        self.didTest = 0

    def getNext (self):
        newmodes = {}

        for depth in self.toggles.keys ():
            newmodes[depth] = []
            for (res, button) in self.toggles[depth]:
                if button.get_active ():
                    newmodes[depth].append (res)

        self.todo.x.modes = newmodes
        
    def testPressed (self, widget, *args):
        newmodes = {}

        for depth in self.toggles.keys ():
            newmodes[depth] = []
            for (res, button) in self.toggles[depth]:
                if button.get_active ():
                    newmodes[depth].append (res)

        self.todo.x.modes = newmodes
        try:
            self.todo.x.test ()
        except RuntimeError:
            ### test failed window
            pass
        else:
            self.didTest = 1

    def numCompare (self, first, second):
        first = string.atoi (first)
        second = string.atoi (second)
        if first > second:
            return 1
        elif first < second:
            return -1
        return 0
    
    def getScreen (self):
        box = GtkVBox (FALSE, 5)
        box.set_border_width (5)

        hbox = GtkHBox (FALSE, 5)

        depths = self.todo.x.modes.keys ()
        depths.sort (self.numCompare)

        self.toggles = {}
        for depth in depths:
            self.toggles[depth] = []
            vbox = GtkVBox (FALSE, 5)
            vbox.pack_start (GtkLabel (depth + _("Bits per Pixel")), FALSE)
            for res in self.todo.x.modes[depth]:
                button = GtkCheckButton (res)
                self.toggles[depth].append (res, button)
                vbox.pack_start (button, FALSE)
                
            hbox.pack_start (vbox)

        
        test = GtkAlignment ()
        button = GtkButton (_("Test this configuration"))
        button.connect ("clicked", self.testPressed)
        test.add (button)
        
        box.pack_start (hbox, FALSE)
        box.pack_start (test, FALSE)
        return box

    def getPrev (self):
        return XConfigWindow
    
class XConfigWindow (InstallWindow):
    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        self.ics.setNextEnabled (TRUE)

        self.todo = ics.getToDo ()
	self.sunServer = 0
	if self.todo.x.server and len (self.todo.x.server) >= 3 and self.todo.x.server[0:3] == 'Sun':
	    self.sunServer = 1
        else:
	    self.sunServer = 0            
        ics.setTitle (_("X Configuration"))
        ics.readHTML ("xconf")
        
        self.didTest = 0

    def getNext (self):
	if not self.__dict__.has_key("monlist"): return None

        if self.monlist:
            if self.monlist.selection:
                row = self.monlist.selection[0]
                setting = self.monlist.get_row_data (row)
                self.todo.x.setMonitor (setting)

	if not self.sunServer:
	    if self.custom.get_active () and not self.skip.get_active ():
		return XCustomWindow
        if not self.skip.get_active ():
            if self.xdm.get_active ():
                self.todo.initlevel = 5
            else:
                self.todo.initlevel = 3
        else:
            self.todo.initlevel = 3
        return None

    def customToggled (self, widget, *args):
        pass
    
    def skipToggled (self, widget, *args):
        self.autoBox.set_sensitive (not widget.get_active ())
        self.todo.x.skip = widget.get_active ()

    def testPressed (self, widget, *args):
        if self.monlist and self.monlist.selection:
	    row = self.monlist.selection[0]
	    setting = self.monlist.get_row_data (row)
	    self.todo.x.setMonitor (setting)

        try:
            self.todo.x.test ()
        except RuntimeError:
            ### test failed window
            pass
        else:
            self.didTest = 1
            
    def getScreen (self):
	if not self.todo.hdList.packages.has_key('XFree86') or \
	   not self.todo.hdList.packages['XFree86'].selected: return None

        self.todo.x.probe ()
        self.todo.x.filterModesByMemory ()
 
        box = GtkVBox (FALSE, 5)
        box.set_border_width (5)

        self.autoBox = GtkVBox (FALSE, 5)

        label = GtkLabel (_("In most cases your video hardware can "
                            "be probed to automatically determine the "
                            "best settings for your display."))
        label.set_justify (JUSTIFY_LEFT)
        label.set_line_wrap (TRUE)        
        label.set_alignment (0.0, 0.5)
        self.autoBox.pack_start (label, FALSE)
        
        label = GtkLabel (_("Autoprobe results:"))
        label.set_alignment (0.0, 0.5)
        self.autoBox.pack_start (label, FALSE)

        report = self.todo.x.probeReport ()
        report = string.replace (report, '\t', '       ')
        
        result = GtkLabel (report)
        result.set_alignment (0.2, 0.5)
        result.set_justify (JUSTIFY_LEFT)
        self.autoBox.pack_start (result, FALSE)

        self.monlist = None
	if ( not self.sunServer ) and self.todo.x.monID == "Generic Monitor":
            label = GtkLabel (_("Your monitor could not be "
                                "autodetected. Please choose it "
                                "from the list below:"))
            label.set_alignment (0.0, 0.5)
            label.set_justify (JUSTIFY_LEFT)
            label.set_line_wrap (TRUE)        
            self.autoBox.pack_start (label, FALSE)

            monitors = self.todo.x.monitors ()
            keys = monitors.keys ()
            keys.sort ()
            self.monlist = GtkCList ()
            self.monlist.set_selection_mode (SELECTION_BROWSE)
	    arch = iutil.getArch()
	    select = 0
                    
            for monitor in keys:
                index = self.monlist.append ((monitor,))
                self.monlist.set_row_data (index, (monitor, monitors[monitor]))
		if arch == 'sparc' and monitor[:3] == 'Sun':
		    self.monlist.select_row (index, 0)
		    select = index
            sw = GtkScrolledWindow ()
            sw.add (self.monlist)
            sw.set_policy (POLICY_NEVER, POLICY_AUTOMATIC)
            self.autoBox.pack_start (sw, TRUE, TRUE)
	    self.monlist.moveto (select, 0, 0.5, 0)

	if not self.sunServer:
	    test = GtkAlignment ()
	    button = GtkButton (_("Test this configuration"))
	    button.connect ("clicked", self.testPressed)
	    test.add (button)
        
	    self.custom = GtkCheckButton (_("Customize X Configuration"))
	    self.custom.connect ("toggled", self.customToggled)

        self.xdm = GtkCheckButton (_("Use Graphical Login"))

        self.skip = GtkCheckButton (_("Skip X Configuration"))
        self.skip.connect ("toggled", self.skipToggled) 

	if not self.sunServer:
	    self.autoBox.pack_start (test, FALSE)
	    self.autoBox.pack_start (self.custom, FALSE)
        self.autoBox.pack_start (self.xdm, FALSE)

        box.pack_start (self.autoBox, TRUE, TRUE)
        box.pack_start (self.skip, FALSE)

        self.skip.set_active (self.todo.x.skip)

        return box
