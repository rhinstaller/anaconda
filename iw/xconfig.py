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

	# I'm not sure what monitors handle this wide aspect resolution, so better play safe
        monName = self.todo.x.monName
	if (self.todo.x.vidRam and self.todo.x.vidRam >= 4096 and
            ((monName and len (monName) >= 11 and monName[:11] == 'Sun 24-inch') or
             self.todo.x.monName == 'Sony GDM-W900')):
	    self.todo.x.modes["8"].append("1920x1200")

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

class MonitorWindow (InstallWindow):
    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)
        self.ics.setNextEnabled (FALSE)
        ics.setTitle (_("Monitor Configuration"))
        ics.readHTML ("monitor")
        self.monitor = None

    def selectCb (self, tree, node, column):
        monitor = tree.node_get_row_data (node)
        if not monitor:
            self.ics.setNextEnabled (FALSE)
            if self.hEntry and self.vEntry:
                self.hEntry.set_text ("")
                self.vEntry.set_text ("")
                self.hEntry.set_editable (FALSE)
                self.vEntry.set_editable (FALSE)
        else:
            self.ics.setNextEnabled (TRUE)
            self.hEntry.set_text (monitor[2])            
            self.vEntry.set_text (monitor[3])
            self.hEntry.set_editable (TRUE)
            self.vEntry.set_editable (TRUE)
            self.monitor = monitor

    def getNext (self):
        if self.skipme:
            return None
        
        if self.monitor:
            self.todo.x.setMonitor ((self.monitor[0],
                                    (self.hEntry.get_text (),
                                     self.vEntry.get_text ())))
        return None

    def moveto (self, ctree, area, node):
        ctree.node_moveto (node, 0, 0.5, 0.0)

    def getScreen (self):
        # Don't configure X in reconfig mode.
        # in regular install, check to see if the XFree86 package is
        # installed.  If it isn't return None.
        if (self.todo.reconfigOnly
            or (not self.todo.hdList.packages.has_key('XFree86')
                or not self.todo.hdList.packages['XFree86'].selected
                or self.todo.serial):
            self.skipme = TRUE
            return None
        
        self.todo.x.probe ()
        box = GtkVBox (FALSE, 5)

        monitors = self.todo.x.monitors ()
        keys = monitors.keys ()
        keys.sort ()
        
        # Monitor selection tree
        ctree = GtkCTree ()
        ctree.set_selection_mode (SELECTION_BROWSE)
        ctree.connect ("tree_select_row", self.selectCb)

        arch = iutil.getArch()

        self.hEntry = GtkEntry ()
        self.vEntry = GtkEntry () 

        select = None
        for man in keys:
            parent = ctree.insert_node (None, None, (man,), 2, is_leaf = FALSE)
            for monitor in monitors[man]:
                node = ctree.insert_node (parent, None, (monitor[0],), 2)
                ctree.node_set_row_data (node, monitor)
                if monitor[0] == self.todo.x.monID:
                    select = node
                    selParent = parent

        # Add a category for a DDC probed monitor that isn't in MonitorDB
        if not select and self.todo.x.monID != "Generic Monitor":
            parent = ctree.insert_node (None, None, ("DDC Probed Monitor",),
                                        2, is_leaf = FALSE)
            node = ctree.insert_node (parent, None, (self.todo.x.monID,), 2)
            monitor = (self.todo.x.monID, self.todo.x.monID, self.todo.x.monHoriz,
                       self.todo.x.monVert)
            ctree.node_set_row_data (node, monitor)
            select = node
            selParent = parent

        if select:
            ctree.select (select)
            ctree.expand (selParent)
            ctree.connect ("draw", self.moveto, select)
        
        sw = GtkScrolledWindow ()
        sw.add (ctree)
        sw.set_policy (POLICY_NEVER, POLICY_AUTOMATIC)
        box.pack_start (sw, TRUE, TRUE)

        # Sync adjustments
        syncbox = GtkHBox (FALSE, 5)
        syncbox.set_border_width (2)

        frame = GtkFrame (_("Horizontal Sync"))
        hbox = GtkHBox (FALSE, 5)
        hbox.set_border_width (2)
        self.hEntry.set_usize (20, -1)
        hbox.pack_start (self.hEntry)
        hbox.pack_start (GtkLabel ("kHz"), FALSE, FALSE)
        frame.add (hbox)
        syncbox.pack_start (frame)

        frame = GtkFrame (_("Vertical Sync"))
        hbox = GtkHBox (FALSE, 5)
        hbox.set_border_width (2)
        self.vEntry.set_usize (20, -1)
        hbox.pack_start (self.vEntry)
        hbox.pack_start (GtkLabel ("Hz"), FALSE, FALSE)
        frame.add (hbox)
        syncbox.pack_start (frame)

        box.pack_start (syncbox, FALSE, FALSE)
        
        return box

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
        if self.skipme:
            return None
        
        if not self.skip.get_active ():
            if self.xdm.get_active ():
                self.todo.initlevel = 5
            else:
                self.todo.initlevel = 3
        else:
            self.todo.initlevel = 3

	if not self.sunServer:
	    if self.custom.get_active () and not self.skip.get_active ():
		return XCustomWindow

        return None

    def customToggled (self, widget, *args):
        pass
    
    def skipToggled (self, widget, *args):
        self.autoBox.set_sensitive (not widget.get_active ())
        self.todo.x.skip = widget.get_active ()

    def testPressed (self, widget, *args):
        try:
            self.todo.x.test ()
        except RuntimeError:
            ### test failed window
            pass
        else:
            self.didTest = 1
            
    def getScreen (self):
        # Don't configure X in reconfig mode.
        # in regular install, check to see if the XFree86 package is
        # installed.  If it isn't return None.
        if (self.todo.reconfigOnly
            or (not self.todo.hdList.packages.has_key('XFree86')
                or not self.todo.hdList.packages['XFree86'].selected
                or self.todo.serial):
            self.skipme = TRUE
            return None

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
        label.set_usize (400, -1)
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
