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

        select = None
        for man in keys:
            parent = ctree.insert_node (None, None, (man,), 2, self.monitor_p, self.monitor_b, self.monitor_p,
                                        self.monitor_b, is_leaf = FALSE)
            
            models = monitors[man]
            models.sort()
            for monitor in models:
                node = ctree.insert_node (parent, None, (monitor[0],), 2)
                ctree.node_set_row_data (node, monitor)
                if monitor[0] == self.todo.x.monID:
                    select = node
                    selParent = parent

        # Add a category for a DDC probed monitor that isn't in MonitorDB
        if not select and self.todo.x.monID != "Generic Monitor":

            parent = ctree.insert_node (None, None, ("DDC Probed Monitor",),
                     2, self.monitor_p, self.monitor_b, self.monitor_p, self.monitor_b, is_leaf = FALSE)

            node = ctree.insert_node (parent, None, (self.todo.x.monID,), 2)
            monitor = (self.todo.x.monID, self.todo.x.monID, self.todo.x.monVert,
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
            self.cardList = GtkCList ()
            self.cardList.set_selection_mode (SELECTION_BROWSE)
            self.cardList.connect ("select_row", self.selectCb)

            self.cards = self.todo.x.cards ()
            cards = self.cards.keys ()
            cards.sort ()
            select = 0
            for card in cards:
                row = self.cardList.append ((card,))
                self.cardList.set_row_data (row, card)
                if self.todo.x.vidCards:
                    if card == self.todo.x.vidCards[self.todo.x.primary]["NAME"]:
                        select = row
                else:
                    if card == "Generic VGA compatible":
                        select = row
            self.cardList.connect ("draw", self.moveto, select)
            sw = GtkScrolledWindow ()
            sw.add (self.cardList)
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
