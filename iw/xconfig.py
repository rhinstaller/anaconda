from gtk import *
from iw import *
from gui import _

import string
import sys

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
        try:
            self.todo.x.test ()
        except RuntimeError:
            ### test failed window
            pass
        else:
            self.didTest = 1
            
        self.setNext ()

    def getScreen (self):
        box = GtkVBox (FALSE, 5)
        box.set_border_width (5)

        hbox = GtkHBox (FALSE, 5)

        depths = self.todo.x.modes.keys ()
        depths.sort ()

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
        button.connect ("pressed", self.testPressed)
        test.add (button)
        
        box.pack_start (hbox, FALSE)
        box.pack_start (test, FALSE)
        return box

    def getPrev (self):
        return XConfigWindow
    
class XConfigWindow (InstallWindow):
    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        self.ics.setNextEnabled (FALSE)

        self.todo = ics.getToDo ()
        ics.setTitle (_("X Configuration"))
        ics.setHTML ("<HTML><BODY>This is the X configuration screen<</BODY></HTML>")

        self.didTest = 0

    def getNext (self):
        if self.monlist:
            if self.monlist.selection:
                row = self.monlist.selection[0]
                setting = self.monlist.get_row_data (row)
                self.todo.x.setMonitor (setting)

        if self.custom.get_active () and not self.skip.get_active ():
            return XCustomWindow
        return None

    def setNext (self):
        if self.skip.get_active () or self.custom.get_active () or self.didTest:
            self.ics.setNextEnabled (TRUE)
        else:
            self.ics.setNextEnabled (FALSE)

    def customToggled (self, widget, *args):
        self.setNext ()

    def skipToggled (self, widget, *args):
        self.autoBox.set_sensitive (not widget.get_active ())
        self.todo.x.skip = widget.get_active ()
        self.setNext ()

    def testPressed (self, widget, *args):
        try:
            self.todo.x.test ()
        except RuntimeError:
            ### test failed window
            pass
        else:
            self.didTest = 1
            
        self.setNext ()

    def getScreen (self):
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

        self.todo.x.monName = None
        self.monlist = None
        if not self.todo.x.monName:
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
                    
            for monitor in keys:
                index = self.monlist.append ((monitor,))
                self.monlist.set_row_data (index, (monitor, monitors[monitor]))
            sw = GtkScrolledWindow ()
            sw.add (self.monlist)
            sw.set_policy (POLICY_NEVER, POLICY_AUTOMATIC)
            self.autoBox.pack_start (sw, TRUE)

        test = GtkAlignment ()
        button = GtkButton (_("Test this configuration"))
        button.connect ("pressed", self.testPressed)
        test.add (button)
        
        self.custom = GtkCheckButton (_("Customize X Configuration"))
        self.custom.connect ("toggled", self.customToggled) 

        self.skip = GtkCheckButton (_("Skip X Configuration"))
        self.skip.connect ("toggled", self.skipToggled) 

        self.autoBox.pack_start (test, FALSE)
        self.autoBox.pack_start (self.custom, FALSE)

        box.pack_start (self.autoBox, FALSE)        
        box.pack_start (self.skip, FALSE)

        self.skip.set_active (self.todo.x.skip)

        return box
