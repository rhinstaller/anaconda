from gtk import *
from iw_gui import *
from translate import _

import string
import sys
import iutil
import xpms_gui

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
        ics.readHTML ("xcustom")
        self.ics.setNextEnabled (TRUE)
        
        self.didTest = 0

    def getNext (self):
        newmodes = {}

        for depth in self.toggles.keys ():
            newmodes[depth] = []
            for (res, button) in self.toggles[depth]:
                if button.get_active ():
                    newmodes[depth].append (res)

        self.todo.x.manualModes = newmodes
        self.todo.x.setModes(newmodes)

    def getPrev (self):
        self.todo.x.setModes(self.oldmodes)

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
        self.oldmodes = self.todo.x.modes
        
        box = GtkVBox (FALSE, 5)
        box.set_border_width (5)

        hbox = GtkHBox (FALSE, 5)

	# I'm not sure what monitors handle this wide aspect resolution, so better play safe
        monName = self.todo.x.monName
	if (self.todo.x.vidRam and self.todo.x.vidRam >= 4096 and
            ((monName and len (monName) >= 11 and monName[:11] == 'Sun 24-inch') or
             self.todo.x.monName == 'Sony GDM-W900')):
	    self.todo.x.modes["8"].append("1920x1200")

        available = self.todo.x.availableModes()
        availableDepths = available.keys()
        availableDepths.sort (self.numCompare)        
        depths = self.todo.x.modes.keys ()
        depths.sort (self.numCompare)

        self.toggles = {}
        for depth in availableDepths:
            self.toggles[depth] = []
            vbox = GtkVBox (FALSE, 5)
            vbox.pack_start (GtkLabel (depth + _("Bits per Pixel")), FALSE)
            for res in available[depth]:
                button = GtkCheckButton (res)
                self.toggles[depth].append (res, button)
                vbox.pack_start (button, FALSE)
                if (self.todo.x.manualModes.has_key(depth)
                    and res in self.todo.x.manualModes[depth]):
                    button.set_active(1)
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
#        self.temp = self.todo.x.monID
#        print "Inisde __init__"

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
            self.vEntry.set_text (monitor[2])
            self.hEntry.set_text (monitor[3])
            self.hEntry.set_editable (TRUE)
            self.vEntry.set_editable (TRUE)
            self.monitor = monitor
            self.todo.x.state = monitor[0]

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
        self.selectCb (ctree, node, -1)

    def getScreen (self):
        # Don't configure X in reconfig mode.
        # in regular install, check to see if the XFree86 package is
        # installed.  If it isn't return None.
        if (self.todo.reconfigOnly
            or (not self.todo.hdList.packages.has_key('XFree86')
                or not self.todo.hdList.packages['XFree86'].selected
                or self.todo.serial)):
            self.skipme = TRUE
            return None
        else:
            self.skipme = FALSE
        
        
        self.todo.x.probe ()
        box = GtkVBox (FALSE, 5)

        monitors = self.todo.x.monitors ()
        keys = monitors.keys ()
        keys.sort ()
        
        # Monitor selection tree
        ctree = GtkCTree ()
        ctree.set_selection_mode (SELECTION_BROWSE)
        ctree.set_expander_style(CTREE_EXPANDER_TRIANGLE)
        ctree.set_line_style(CTREE_LINES_NONE)
        ctree.connect ("tree_select_row", self.selectCb)

        self.monitor_p, self.monitor_b = create_pixmap_from_xpm_d (ctree, None, xpms_gui.MONITOR_XPM)

        arch = iutil.getArch()

        self.hEntry = GtkEntry ()
        self.vEntry = GtkEntry () 

        # If the user has not changed monitor setting before, set the state info to the probed value
        if self.todo.x.state == "":
            self.todo.x.state = self.todo.x.monID

        select = None
        for man in keys:
            parent = ctree.insert_node (None, None, (man,), 2, self.monitor_p, self.monitor_b, self.monitor_p,
                                        self.monitor_b, is_leaf = FALSE)
            
            models = monitors[man]
            models.sort()
            for monitor in models:
                node = ctree.insert_node (parent, None, (monitor[0],), 2)
                ctree.node_set_row_data (node, monitor)
#                if monitor[0] == self.todo.x.monID:
                if monitor[0] == self.todo.x.state:
                    select = node
                    selParent = parent

        # Add a category for a DDC probed monitor that isn't in MonitorDB
#        if not select and self.todo.x.monID != "Generic Monitor":
        if not select and self.todo.x.monID != "Generic Monitor":
            
            parent = ctree.insert_node (None, None, ("DDC Probed Monitor",),
                     2, self.monitor_p, self.monitor_b, self.monitor_p, self.monitor_b, is_leaf = FALSE)

#            node = ctree.insert_node (parent, None, (self.todo.x.monID,), 2)
#            monitor = (self.todo.x.monID, self.todo.x.monID, self.todo.x.monVert,
#                       self.todo.x.monHoriz)

            node = ctree.insert_node (parent, None, (self.todo.x.state,), 2)
            monitor = (self.todo.x.state, self.todo.x.state, self.todo.x.monVert,
                       self.todo.x.monHoriz)




            ctree.node_set_row_data (node, monitor)
            select = node
            selParent = parent

        if select:
            ctree.select (select)
            ctree.expand (selParent)
            ctree.connect ("draw", self.moveto, select)

        self.hEntry.set_text (self.todo.x.monHoriz)
        self.vEntry.set_text (self.todo.x.monVert)        

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

        self.todo.instClass.setDesktop(self.newDesktop)

        if not self.skip.get_active ():
            if self.xdm.get_active ():
                self.todo.initlevel = 5
            else:
                self.todo.initlevel = 3
        else:
            self.todo.initlevel = 3

	if not self.cantprobe:
	    if self.custom.get_active () and not self.skip.get_active ():
		return XCustomWindow

        return None

    def customToggled (self, widget, *args):
        pass
    
    def skipToggled (self, widget, *args):
        self.configbox.set_sensitive (not widget.get_active ())
        self.todo.x.skip = widget.get_active ()

    def testPressed (self, widget, *args):
        try:
            self.todo.x.test ()
        except RuntimeError:
            ### test failed window
            pass
        else:
            self.didTest = 1

    def memory_cb (self, widget, size):
        self.todo.x.vidRam = size[:-1]
        self.todo.x.filterModesByMemory ()

    def moveto (self, clist, area, row):
        clist.select_row (row, 0)
        clist.moveto (row, 0, 0.5, 0.0)


    def selectCb (self, list, row, col, event):
        cardname = list.get_row_data (row)
        if cardname:
            card = self.cards[cardname]
            depth = 0
            while depth < 16 and card.has_key ("SEE"):
                card = self.cards[card["SEE"]]
                depth = depth + 1
            self.todo.x.setVidcard (card)

    def desktopCb (self, widget, desktop):
        self.newDesktop = desktop
        
    def getScreen (self):
        # Don't configure X in reconfig mode.
        # in regular install, check to see if the XFree86 package is
        # installed.  If it isn't return None.
        if (self.todo.reconfigOnly
            or (not self.todo.hdList.packages.has_key('XFree86')
                or not self.todo.hdList.packages['XFree86'].selected
                or self.todo.serial)):
            self.skipme = TRUE
            return None
        else:
            self.skipme = FALSE

        self.newDesktop = ""
        self.todo.x.probe ()
        self.todo.x.filterModesByMemory ()

        box = GtkVBox (FALSE, 0)
        box.set_border_width (0)

        self.autoBox = GtkVBox (FALSE, 5)

        arch = iutil.getArch()
        if arch == "alpha":
            label = GtkLabel (_("Your video ram size can not be autodetected.  "
                                "Choose your video ram size from the choices below:"))
            label.set_justify (JUSTIFY_LEFT)
            label.set_line_wrap (TRUE)        
            label.set_alignment (0.0, 0.5)
            label.set_usize (400, -1)
            box.pack_start (label, FALSE)
        elif arch == "i386":
            # but we can on everything else
            self.autoBox = GtkVBox (FALSE, 5)

            label = GtkLabel (_("In most cases your video hardware can "
                                "be probed to automatically determine the "
                                "best settings for your display."))
            label.set_justify (JUSTIFY_LEFT)
            label.set_line_wrap (TRUE)        
            label.set_alignment (0.0, 0.5)
            label.set_usize (400, -1)
            self.autoBox.pack_start (label, FALSE)

            label = GtkLabel (_("If the probed settings do not match your hardware "
                                "select the correct setting below:"))
            label.set_justify (JUSTIFY_LEFT)
            label.set_line_wrap (TRUE)        
            label.set_alignment (0.0, 0.5)
            label.set_usize (400, -1)
            self.autoBox.pack_start (label, FALSE)

            box.pack_start (self.autoBox, FALSE)
        else:
            # sparc
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
            box.pack_start (self.autoBox, FALSE)
            
        # card configuration
        if arch == "i386" or arch == "alpha":

        # Monitor selection tree
            ctree = GtkCTree ()
            ctree.set_selection_mode (SELECTION_BROWSE)
            ctree.set_expander_style(CTREE_EXPANDER_TRIANGLE)
            ctree.set_line_style(CTREE_LINES_NONE)
#            ctree.connect ("tree_select_row", self.selectCb)

            self.videocard_p, self.videocard_b = create_pixmap_from_xpm_d (ctree, None, xpms_gui.VIDEOCARD_XPM)

            manufacturer = ["AOpen", "ASUS", "ATI", "Actix", "Ark Logic", "Avance Logic", "Compaq",
                            "Canopus", "Cardex", "Chaintech", "Chips & Technologies", "Cirrus", "Creative Labs",
                            "DFI", "DSV", "DataExpert", "Dell", "Diamond", "Digital", "ELSA", "EONtronics",
                            "Epson", "ExpertColor", "Gainward", "Generic", "Genoa", "Hercules", "Intel",
                            "Jaton", "LeadTek", "MELCO", "MachSpeed", "Matrox", "Miro", "NVIDIA", "NeoMagic",
                            "Number Nine", "Oak", "Octek", "Orchid", "Paradise", "PixelView", "Quantum",
                            "RIVA", "Real3D", "Rendition", "S3", "Sharp", "SMI", "SNI", "SPEA", "STB", "SiS",
                            "Sierra", "Sigma", "Soyo", "Spider", "Sun", "TechWorks", "Toshiba", "Trident",
                            "VideoLogic", "ViewTop", "Voodoo", "WD", "WinFast"]     

            parents = ["AOpen", "ASUS", "ATI", "Actix", "Ark Logic", "Avance Logic", "Compaq",
                            "Canopus", "Cardex", "Chaintech", "Chips & Technologies", "Cirrus", "Creative Labs",
                            "DFI", "DSV", "DataExpert", "Dell", "Diamond", "Digital", "ELSA", "EONtronics",
                            "Epson", "ExpertColor", "Gainward", "Generic", "Genoa", "Hercules", "Intel",
                            "Jaton", "LeadTek", "MELCO", "MachSpeed", "Matrox", "Miro", "NVIDIA", "NeoMagic",
                            "Number Nine", "Oak", "Octek", "Orchid", "Paradise", "PixelView", "Quantum",
                            "RIVA", "Real3D", "Rendition", "S3", "Sharp", "SMI", "SNI", "SPEA", "STB", "SiS",
                            "Sierra", "Sigma", "Soyo", "Spider", "Sun", "TechWorks", "Toshiba", "Trident",
                            "VideoLogic", "ViewTop", "Voodoo", "WD", "WinFast"]
#            for man in manufacturer:
#                for parent in parents:
                    
#                print man
#                    parent = ctree.insert_node (None, None, (man,), 2, self.videocard_p, self.videocard_b,
#                                                self.videocard_p, self.videocard_b, FALSE)
 

                
            aopen = ctree.insert_node (None, None, ("AOpen",), 2, self.videocard_p, self.videocard_b,
                                        self.videocard_p, self.videocard_b, FALSE)
            asus = ctree.insert_node (None, None, ("ASUS ",), 2, self.videocard_p, self.videocard_b,
                                        self.videocard_p, self.videocard_b, FALSE)
            ati = ctree.insert_node (None, None, ("ATI",), 2, self.videocard_p, self.videocard_b,
                                        self.videocard_p, self.videocard_b, FALSE)
            actix = ctree.insert_node (None, None, ("Actix ",), 2, self.videocard_p, self.videocard_b,
                                        self.videocard_p, self.videocard_b, FALSE)
            arklogic = ctree.insert_node (None, None, ("Ark Logic ",), 2, self.videocard_p, self.videocard_b,
                                        self.videocard_p, self.videocard_b, FALSE)
            avancelogic = ctree.insert_node (None, None, ("Avance Logic ",), 2, self.videocard_p, self.videocard_b,
                                        self.videocard_p, self.videocard_b, FALSE)
            compaq = ctree.insert_node (None, None, ("Compaq",), 2, self.videocard_p, self.videocard_b,
                                        self.videocard_p, self.videocard_b, FALSE)
            canopus = ctree.insert_node (None, None, ("Canopus",), 2, self.videocard_p, self.videocard_b,
                                         self.videocard_p, self.videocard_b, FALSE)
            cardex = ctree.insert_node (None, None, ("Cardex",), 2, self.videocard_p, self.videocard_b,
                                        self.videocard_p, self.videocard_b, FALSE)
            chaintech = ctree.insert_node (None, None, ("Chaintech",), 2, self.videocard_p, self.videocard_b,
                                           self.videocard_p, self.videocard_b, FALSE)
            cnt = ctree.insert_node (None, None, ("Chips & Technologies",), 2, self.videocard_p, self.videocard_b,
                                     self.videocard_p, self.videocard_b, FALSE)
            cirrus = ctree.insert_node (None, None, ("Cirrus",), 2, self.videocard_p, self.videocard_b,
                                        self.videocard_p, self.videocard_b, FALSE)
            creativelabs = ctree.insert_node (None, None, ("Creative Labs",), 2, self.videocard_p, self.videocard_b,
                                              self.videocard_p, self.videocard_b, FALSE)
            dfi = ctree.insert_node (None, None, ("DFI",), 2, self.videocard_p, self.videocard_b,
                                     self.videocard_p, self.videocard_b, FALSE)
            dsv = ctree.insert_node (None, None, ("DSV",), 2, self.videocard_p, self.videocard_b,
                                     self.videocard_p, self.videocard_b, FALSE)
            dataexpert = ctree.insert_node (None, None, ("Data Expert",), 2, self.videocard_p, self.videocard_b,
                                            self.videocard_p, self.videocard_b, FALSE)
            dell = ctree.insert_node (None, None, ("Dell",), 2, self.videocard_p, self.videocard_b,
                                      self.videocard_p, self.videocard_b, FALSE)
            diamond = ctree.insert_node (None, None, ("Diamond",), 2, self.videocard_p, self.videocard_b,
                                         self.videocard_p, self.videocard_b, FALSE)
            digital = ctree.insert_node (None, None, ("Digital",), 2, self.videocard_p, self.videocard_b,
                                         self.videocard_p, self.videocard_b, FALSE)
            elsa = ctree.insert_node (None, None, ("ELSA",), 2, self.videocard_p, self.videocard_b,
                                      self.videocard_p, self.videocard_b, FALSE)
            eontronics = ctree.insert_node (None, None, ("EONtronics",), 2, self.videocard_p, self.videocard_b,
                                            self.videocard_p, self.videocard_b, FALSE)
            epson = ctree.insert_node (None, None, ("Epson",), 2, self.videocard_p, self.videocard_b,
                                       self.videocard_p, self.videocard_b, FALSE)
            expertcolor = ctree.insert_node (None, None, ("ExpertColor",), 2, self.videocard_p, self.videocard_b,
                                             self.videocard_p, self.videocard_b, FALSE)
            gainward = ctree.insert_node (None, None, ("Gainward",), 2, self.videocard_p, self.videocard_b,
                                          self.videocard_p, self.videocard_b, FALSE)
            generic = ctree.insert_node (None, None, ("Generic",), 2, self.videocard_p, self.videocard_b,
                                         self.videocard_p, self.videocard_b, FALSE)
            genoa = ctree.insert_node (None, None, ("Genoa",), 2, self.videocard_p, self.videocard_b,
                                       self.videocard_p, self.videocard_b, FALSE)
            hercules = ctree.insert_node (None, None, ("Hercules",), 2, self.videocard_p, self.videocard_b,
                                          self.videocard_p, self.videocard_b, FALSE)
            intel = ctree.insert_node (None, None, ("Intel",), 2, self.videocard_p, self.videocard_b,
                                       self.videocard_p, self.videocard_b, FALSE)
            jaton = ctree.insert_node (None, None, ("Jaton",), 2, self.videocard_p, self.videocard_b,
                                       self.videocard_p, self.videocard_b, FALSE)
            leadtek = ctree.insert_node (None, None, ("LeadTek",), 2, self.videocard_p, self.videocard_b,
                                         self.videocard_p, self.videocard_b, FALSE)
            melco = ctree.insert_node (None, None, ("MELCO",), 2, self.videocard_p, self.videocard_b,
                                       self.videocard_p, self.videocard_b, FALSE)
            machspeed = ctree.insert_node (None, None, ("MachSpeed",), 2, self.videocard_p, self.videocard_b,
                                           self.videocard_p, self.videocard_b, FALSE)
            matrox = ctree.insert_node (None, None, ("Matrox",), 2, self.videocard_p, self.videocard_b,
                                        self.videocard_p, self.videocard_b, FALSE)
            miro = ctree.insert_node (None, None, ("Miro",), 2, self.videocard_p, self.videocard_b,
                                      self.videocard_p, self.videocard_b, FALSE)
            nvidia = ctree.insert_node (None, None, ("NVIDIA",), 2, self.videocard_p, self.videocard_b,
                                        self.videocard_p, self.videocard_b, FALSE)
            neomagic = ctree.insert_node (None, None, ("NeoMagic",), 2, self.videocard_p, self.videocard_b,
                                          self.videocard_p, self.videocard_b, FALSE)
            numbernine = ctree.insert_node (None, None, ("Number Nine",), 2, self.videocard_p, self.videocard_b,
                                            self.videocard_p, self.videocard_b, FALSE)
            oak = ctree.insert_node (None, None, ("Oak",), 2, self.videocard_p, self.videocard_b,
                                     self.videocard_p, self.videocard_b, FALSE)
            octek = ctree.insert_node (None, None, ("Octek",), 2, self.videocard_p, self.videocard_b,
                                       self.videocard_p, self.videocard_b, FALSE)
            orchid = ctree.insert_node (None, None, ("Orchid",), 2, self.videocard_p, self.videocard_b,
                                        self.videocard_p, self.videocard_b, FALSE)
            other = ctree.insert_node (None, None, ("Other",), 2, self.videocard_p, self.videocard_b,
                                        self.videocard_p, self.videocard_b, FALSE)
            paradise = ctree.insert_node (None, None, ("Paradise",), 2, self.videocard_p, self.videocard_b,
                                          self.videocard_p, self.videocard_b, FALSE)
            pixelview = ctree.insert_node (None, None, ("PixelView",), 2, self.videocard_p, self.videocard_b,
                                           self.videocard_p, self.videocard_b, FALSE)
            quantum = ctree.insert_node (None, None, ("Quantum",), 2, self.videocard_p, self.videocard_b,
                                         self.videocard_p, self.videocard_b, FALSE)
            riva = ctree.insert_node (None, None, ("RIVA",), 2, self.videocard_p, self.videocard_b,
                                      self.videocard_p, self.videocard_b, FALSE)
            real3D = ctree.insert_node (None, None, ("Real3D",), 2, self.videocard_p, self.videocard_b,
                                        self.videocard_p, self.videocard_b, FALSE)
            rendition = ctree.insert_node (None, None, ("Rendition",), 2, self.videocard_p, self.videocard_b,
                                           self.videocard_p, self.videocard_b, FALSE)
            s3 = ctree.insert_node (None, None, ("S3",), 2, self.videocard_p, self.videocard_b,
                                    self.videocard_p, self.videocard_b, FALSE)
            sharp = ctree.insert_node (None, None, ("Sharp",), 2, self.videocard_p, self.videocard_b,
                                       self.videocard_p, self.videocard_b, FALSE)
            smi = ctree.insert_node (None, None, ("SMI",), 2, self.videocard_p, self.videocard_b,
                                     self.videocard_p, self.videocard_b, FALSE)
            sni = ctree.insert_node (None, None, ("SNI",), 2, self.videocard_p, self.videocard_b,
                                     self.videocard_p, self.videocard_b, FALSE)
            spea = ctree.insert_node (None, None, ("SPEA",), 2, self.videocard_p, self.videocard_b,
                                      self.videocard_p, self.videocard_b, FALSE)
            stb = ctree.insert_node (None, None, ("STB",), 2, self.videocard_p, self.videocard_b,
                                     self.videocard_p, self.videocard_b, FALSE)
            sis = ctree.insert_node (None, None, ("SiS",), 2, self.videocard_p, self.videocard_b,
                                     self.videocard_p, self.videocard_b, FALSE)
            sierra = ctree.insert_node (None, None, ("Sierra",), 2, self.videocard_p, self.videocard_b,
                                        self.videocard_p, self.videocard_b, FALSE)
            sigma = ctree.insert_node (None, None, ("Sigma",), 2, self.videocard_p, self.videocard_b,
                                       self.videocard_p, self.videocard_b, FALSE)
            soyo = ctree.insert_node (None, None, ("Soyo",), 2, self.videocard_p, self.videocard_b,
                                      self.videocard_p, self.videocard_b, FALSE)
            spider = ctree.insert_node (None, None, ("Spider",), 2, self.videocard_p, self.videocard_b,
                                        self.videocard_p, self.videocard_b, FALSE)
            sun = ctree.insert_node (None, None, ("Sun",), 2, self.videocard_p, self.videocard_b,
                                     self.videocard_p, self.videocard_b, FALSE)
            techworks = ctree.insert_node (None, None, ("TechWorks",), 2, self.videocard_p, self.videocard_b,
                                           self.videocard_p, self.videocard_b, FALSE)
            toshiba = ctree.insert_node (None, None, ("Toshiba",), 2, self.videocard_p, self.videocard_b,
                                         self.videocard_p, self.videocard_b, FALSE)
            trident = ctree.insert_node (None, None, ("Trident",), 2, self.videocard_p, self.videocard_b,
                                         self.videocard_p, self.videocard_b, FALSE)
            videologic = ctree.insert_node (None, None, ("VideoLogic",), 2, self.videocard_p, self.videocard_b,
                                            self.videocard_p, self.videocard_b, FALSE)
            viewtop = ctree.insert_node (None, None, ("ViewTop",), 2, self.videocard_p, self.videocard_b,
                                         self.videocard_p, self.videocard_b, FALSE)
            voodoo = ctree.insert_node (None, None, ("Voodoo",), 2, self.videocard_p, self.videocard_b,
                                        self.videocard_p, self.videocard_b, FALSE)
            wd = ctree.insert_node (None, None, ("WD",), 2, self.videocard_p, self.videocard_b,
                                    self.videocard_p, self.videocard_b, FALSE)
            winfast = ctree.insert_node (None, None, ("WinFast",), 2, self.videocard_p, self.videocard_b,
                                         self.videocard_p, self.videocard_b, FALSE)


            self.cardList = GtkCList ()
            self.cardList.set_selection_mode (SELECTION_BROWSE)
            self.cardList.connect ("select_row", self.selectCb)

            self.cards = self.todo.x.cards ()
            cards = self.cards.keys ()
            cards.sort ()
            select = 0


#            print parent
            for card in cards:
                
                temp = string.lower(card)
#                print card[:5]
#                print temp
#                print manufacturer[1]

                if temp[:5] == "aopen":
                    node = ctree.insert_node (aopen, None, (card,), 2)
#                    print card
                elif temp[:4] == "asus":
                    node = ctree.insert_node (asus, None, (card,), 2)
                elif temp[:3] == "ati":
                    node = ctree.insert_node (ati, None, (card,), 2)
                elif temp[:5] == "actix":
                    node = ctree.insert_node (actix, None, (card,), 2)
                elif temp[:9] == "ark logic":
                    node = ctree.insert_node (arklogic, None, (card,), 2)
                elif temp[:12] == "avance logic":
                    node = ctree.insert_node (avancelogic, None, (card,), 2)
                elif temp[:6] == "compaq":
                    node = ctree.insert_node (compaq, None, (card,), 2)
                elif temp[:7] == "canopus":
                    node = ctree.insert_node (canopus, None, (card,), 2)
                elif temp[:6] == "cardex":
                    node = ctree.insert_node (cardex, None, (card,), 2)
                elif temp[:9] == "chaintech":
                    node = ctree.insert_node (chaintech, None, (card,), 2)
                elif temp[:5] == "chips":
                    node = ctree.insert_node (cnt, None, (card,), 2)
                elif temp[:6] == "cirrus":
                    node = ctree.insert_node (cirrus, None, (card,), 2)
                elif temp[:8] == "creative":
                    node = ctree.insert_node (creativelabs, None, (card,), 2)
                elif temp[:3] == "dfi":
                    node = ctree.insert_node (dfi, None, (card,), 2)
                elif temp[:3] == "dsv":
                    node = ctree.insert_node (dsv, None, (card,), 2)
                elif temp[:4] == "data":
                    node = ctree.insert_node (dataexpert, None, (card,), 2)
                elif temp[:4] == "dell":
                    node = ctree.insert_node (dell, None, (card,), 2)
                elif temp[:7] == "diamond":
                    node = ctree.insert_node (diamond, None, (card,), 2)
                elif temp[:7] == "digital":
                    node = ctree.insert_node (digital, None, (card,), 2)
                elif temp[:4] == "elsa":
                    node = ctree.insert_node (elsa, None, (card,), 2)
                elif temp[:10] == "eontronics":
                    node = ctree.insert_node (eontronics, None, (card,), 2)
                elif temp[:5] == "epson":
                    node = ctree.insert_node (epson, None, (card,), 2)
                elif temp[:11] == "expertcolor":
                    node = ctree.insert_node (expertcolor, None, (card,), 2)
                elif temp[:8] == "gainward":
                    node = ctree.insert_node (gainward, None, (card,), 2)
                elif temp[:7] == "generic":
                    node = ctree.insert_node (generic, None, (card,), 2)
                elif temp[:5] == "genoa":
                    node = ctree.insert_node (genoa, None, (card,), 2)
                elif temp[:8] == "hercules":
                    node = ctree.insert_node (hercules, None, (card,), 2)
                elif temp[:5] == "intel":
                    node = ctree.insert_node (intel, None, (card,), 2)
                elif temp[:5] == "jaton":
                    node = ctree.insert_node (jaton, None, (card,), 2)
                elif temp[:7] == "leadtek":
                    node = ctree.insert_node (leadtek, None, (card,), 2)
                elif temp[:5] == "melco":
                    node = ctree.insert_node (melco, None, (card,), 2)
                elif temp[:9] == "machspeed":
                    node = ctree.insert_node (machspeed, None, (card,), 2)
                elif temp[:6] == "matrox":
                    node = ctree.insert_node (matrox, None, (card,), 2)
                elif temp[:4] == "miro":
                    node = ctree.insert_node (miro, None, (card,), 2)
                elif temp[:6] == "nvidia":
                    node = ctree.insert_node (nvidia, None, (card,), 2)
                elif temp[:8] == "neomagic":
                    node = ctree.insert_node (neomagic, None, (card,), 2)
                elif temp[:6] == "number":
                    node = ctree.insert_node (numbernine, None, (card,), 2)
                elif temp[:3] == "oak":
                    node = ctree.insert_node (oak, None, (card,), 2)
                elif temp[:5] == "octek":
                    node = ctree.insert_node (octek, None, (card,), 2)
                elif temp[:6] == "orchid":
                    node = ctree.insert_node (orchid, None, (card,), 2)
                elif temp[:8] == "paradise":
                    node = ctree.insert_node (paradise, None, (card,), 2)
                elif temp[:9] == "pixelview":
                    node = ctree.insert_node (pixelview, None, (card,), 2)
                elif temp[:7] == "quantum":
                    node = ctree.insert_node (quantum, None, (card,), 2)
                elif temp[:4] == "riva":
                    node = ctree.insert_node (riva, None, (card,), 2)
                elif temp[:6] == "real3d":
                    node = ctree.insert_node (real3D, None, (card,), 2)
                elif temp[:9] == "rendition":
                    node = ctree.insert_node (rendition, None, (card,), 2)
                elif temp[:2] == "s3":
                    node = ctree.insert_node (s3, None, (card,), 2)
                elif temp[:5] == "sharp":
                    node = ctree.insert_node (sharp, None, (card,), 2)
                elif temp[:3] == "smi":
                    node = ctree.insert_node (smi, None, (card,), 2)
                elif temp[:3] == "sni":
                    node = ctree.insert_node (sni, None, (card,), 2)
                elif temp[:4] == "spea":
                    node = ctree.insert_node (spea, None, (card,), 2)
                elif temp[:3] == "stb":
                    node = ctree.insert_node (stb, None, (card,), 2)
                elif temp[:3] == "sis":
                    node = ctree.insert_node (sis, None, (card,), 2)
                elif temp[:6] == "sierra":
                    node = ctree.insert_node (sierra, None, (card,), 2)
                elif temp[:5] == "sigma":
                    node = ctree.insert_node (sigma, None, (card,), 2)
                elif temp[:4] == "soyo":
                    node = ctree.insert_node (soyo, None, (card,), 2)
                elif temp[:6] == "spider":
                    node = ctree.insert_node (spider, None, (card,), 2)
                elif temp[:3] == "sun":
                    node = ctree.insert_node (sun, None, (card,), 2)
                elif temp[:9] == "techworks":
                    node = ctree.insert_node (techworks, None, (card,), 2)
                elif temp[:7] == "toshiba":
                    node = ctree.insert_node (toshiba, None, (card,), 2)
                elif temp[:7] == "trident":
                    node = ctree.insert_node (trident, None, (card,), 2)
                elif temp[:10] == "videologic":
                    node = ctree.insert_node (videologic, None, (card,), 2)
                elif temp[:7] == "viewtop":
                    node = ctree.insert_node (viewtop, None, (card,), 2)
                elif temp[:6] == "voodoo":
                    node = ctree.insert_node (voodoo, None, (card,), 2)
                elif temp[:2] == "wd":
                    node = ctree.insert_node (wd, None, (card,), 2)
                elif temp[:7] == "winfast":
                    node = ctree.insert_node (winfast, None, (card,), 2)
                else:
                    node = ctree.insert_node (other, None, (card,), 2)





                    
            for card in cards:
                row = self.cardList.append ((card,))
                self.cardList.set_row_data (row, card)
#                print "Row = ", row
#                print "Card = ", card
                if self.todo.x.vidCards:
                    if card == self.todo.x.vidCards[self.todo.x.primary]["NAME"]:
                        select = row
                else:
                    if card == "Generic VGA compatible":
                        select = row
            self.cardList.connect ("draw", self.moveto, select)
            sw = GtkScrolledWindow ()
#            sw.add (self.cardList)
            sw.add (ctree)
            box.pack_start (sw, TRUE)




            # Memory configuration table
            table = GtkTable()
            group = None
            count = 0
            for size in ("256k", "512k", "1024k", "2048k", "4096k",
                         "8192k", "16384k", "32768k"):
                button = GtkRadioButton (group, size)
                button.connect ('clicked', self.memory_cb, size)
                if size[:-1] == self.todo.x.vidRam:
                    button.set_active (1)
                if not group:
                    group = button
                table.attach (button, count % 4, (count % 4) + 1,
                              count / 4, (count / 4) + 1)
                count = count + 1
            box.pack_start (table, FALSE)
        optbox = GtkVBox (FALSE, 5)


        # cannot reliably test on i810 or Voodoo driver, or on Suns who dont
        # need it since they are fixed resolution

        self.cantprobe = 0
        if not self.sunServer and self.todo.x.vidCards:
            if self.todo.x.vidCards[self.todo.x.primary].has_key("DRIVER"):
                curdriver = self.todo.x.vidCards[self.todo.x.primary]["DRIVER"]
                noprobedriverList = ("i810", "tdfx")
                for adriver in noprobedriverList:
                    if curdriver == adriver:
                        self.cantprobe = 1
        else:
            self.cantprobe = 1


        if not self.cantprobe:
            test = GtkAlignment ()
            button = GtkButton (_("Test this configuration"))
            button.connect ("clicked", self.testPressed)
            test.add (button)
            box.pack_start (test, FALSE)

            self.custom = GtkCheckButton (_("Customize X Configuration"))
            self.custom.connect ("toggled", self.customToggled)
            optbox.pack_start (self.custom, FALSE)

        self.xdm = GtkCheckButton (_("Use Graphical Login"))
        self.skip = GtkCheckButton (_("Skip X Configuration"))
        self.skip.connect ("toggled", self.skipToggled) 

        optbox.pack_start (self.xdm, FALSE)

        hbox = GtkHBox (TRUE, 5)
        hbox.pack_start (optbox, FALSE)

        self.desktop = None
        if ((self.todo.hdList.has_key('gnome-core')
             and self.todo.hdList['gnome-core'].selected)
            and (self.todo.hdList.has_key('kdebase')
                 and self.todo.hdList['kdebase'].selected)):
            def pixlabel (ics, label, pixmap):
                im = ics.readPixmap (pixmap)
                if im:
                    im.render ()
                    pix = im.make_pixmap ()
                    hbox = GtkHBox (FALSE, 5)
                    hbox.pack_start (pix, FALSE, FALSE, 0)
                    label = GtkLabel (label)
                    label.show()
                    label.set_alignment (0.0, 0.5)
                    hbox.pack_start (label, TRUE, TRUE, 15)
                    hbox.show()
                    return hbox
                else:
                    return GtkLabel (label)
            
            option = GtkOptionMenu()
            menu = GtkMenu()
            gnome = GtkMenuItem()
            gnome.add (pixlabel (self.ics, "GNOME", "gnome-mini.png"))
            gnome.connect ("activate", self.desktopCb, "GNOME")
            kde = GtkMenuItem()
            kde.add (pixlabel (self.ics, "KDE", "kde-mini.png"))
            kde.connect ("activate", self.desktopCb, "KDE")            
            menu.add (gnome)
            menu.add (kde)
            if self.todo.instClass.getDesktop() == "KDE":
                self.newDesktop = "KDE"
                menu.set_active (1)
            else:
                self.newDesktop = "GNOME"
                menu.set_active (0)
            option.set_menu (menu)
            v = GtkVBox (FALSE, 5)
            l = GtkLabel (_("Default Desktop:"))
            l.set_alignment (0.0, 0.5)
            v.pack_start (l, FALSE)
            v.pack_start (option, TRUE)
            hbox.pack_start (v, FALSE)

        box.pack_start (hbox, FALSE)

        self.topbox = GtkVBox (FALSE, 5)
        self.topbox.set_border_width (5)
        self.topbox.pack_start (box, TRUE, TRUE)
        self.topbox.pack_start (self.skip, FALSE)

        self.configbox = box

        self.skip.set_active (self.todo.x.skip)

        return self.topbox
