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

    def color_cb(self, widget, data):
#        print data, " bit color depth selected"
#        print self.depth_combo.list.child_position (data)
        depth = self.depth_combo.list.child_position (data)

        if depth == 0:
            self.res_combo.set_popdown_strings (self.avail_res1)
        if depth == 1:
            self.res_combo.set_popdown_strings (self.avail_res2)        
        if depth == 2:
            self.res_combo.set_popdown_strings (self.avail_res3)
    
    def res_cb (self, widget, data):
        pass
#        print data, " resolution was selected"
#        print self.res_combo.list.child_position (data)

    def desktop_cb (self, widget, desktop):
        self.newDesktop = desktop
        print desktop

        if desktop == "GNOME":
            im = self.ics.readPixmap ("gnome.png")
        elif desktop == "KDE":
            im = self.ics.readPixmap ("kde.png")            

        self.vbox4.destroy ()

        self.vbox4 = GtkVBox ()

        if im:
            im.render ()
            pix = im.make_pixmap ()
            a = GtkAlignment ()
            a.add (pix)
            a.set (0.5, 0.5, 1.0, 1.0)
            self.vbox4.pack_start (a, TRUE, TRUE)

        self.hbox4.pack_start (self.vbox4)
        self.hbox4.show_all ()

    def getScreen (self):
        self.oldmodes = self.todo.x.modes
        
        box = GtkVBox (FALSE, 5)
        box.set_border_width (5)

        hbox1 = GtkHBox (FALSE, 5)
        hbox2 = GtkHBox (FALSE, 5)
        hbox3 = GtkHBox (FALSE, 5)



        im = self.ics.readPixmap ("monitor.png")
        if im:
            im.render ()
            pix = im.make_pixmap ()
            a = GtkAlignment ()
            a.add (pix)
            a.set (0.5, 0.5, 1.0, 1.0)
            hbox1.pack_start (a, TRUE, TRUE)


        available = self.todo.x.availableModes()
        availableDepths = available.keys()
        availableDepths.sort (self.numCompare)        
        depths = self.todo.x.modes.keys ()
        depths.sort (self.numCompare)


        self.depth_count = 0
        self.res_count1 = 0
        self.res_count2 = 0
        self.res_count3 = 0

        for depth in availableDepths:
#            print "depth = ", depth

            for res in available[depth]:
#                print "res = ", res
                if self.depth_count == 0:
                    self.res_count1 = self.res_count1 + 1
                if self.depth_count == 1:
                    self.res_count2 = self.res_count2 + 1                    
                if self.depth_count == 2:
                    self.res_count3 = self.res_count1 + 1

            self.depth_count = self.depth_count + 1

        if self.res_count1 == 0:
            self.depth_count = self.depth_count - 1
        if self.res_count2 == 0:
            self.depth_count = self.depth_count - 1        
        if self.res_count3 == 0:
            self.depth_count = self.depth_count - 1
            
#        print self.depth_count 
#        print self.res_count1 
#        print self.res_count2 
#        print self.res_count3 



        frame1 = GtkFrame (_("Color Depths"))
        frame1.set_border_width (10)
        vbox1 = GtkVBox ()
        frame1.add (vbox1)
        hbox2.pack_start (frame1, TRUE, FALSE, 10)

        depth_list = ["256 Colors (8 Bit)", "High Color (16 Bit)", "True Color (24 Bit)"]

        self.avail_depths = depth_list[:self.depth_count]
#        print self.avail_depths
    

        self.depth_combo = GtkCombo ()
        self.depth_combo.set_popdown_strings (self.avail_depths)
        self.depth_combo.list.connect ("select-child", self.color_cb)
        vbox1.pack_start (self.depth_combo, TRUE, FALSE, 10)

#        im = self.ics.readPixmap ("spectrum.png")
#        if im:
#            im.render ()
#            pix = im.make_pixmap ()
#            a = GtkAlignment ()
#            a.add (pix)
#            a.set (0.5, 0.5, 1.0, 1.0)
#            vbox1.pack_start (a, TRUE, TRUE)

        frame2 = GtkFrame (_("Screen Resolution"))
        frame2.set_border_width (10)
        vbox2 = GtkVBox ()
        frame2.add (vbox2)
        hbox2.pack_start (frame2, TRUE, FALSE, 10)


        res_list = ["640x480", "800x600", "1024x768", "1152x864", "1280x1024", "1600x1200"]

        self.avail_res1 = res_list[:self.res_count1]
        self.avail_res2 = res_list[:self.res_count2]
        self.avail_res3 = res_list[:self.res_count3]

#        print "8 bit res = ", self.avail_res1
#        print "16 bit res = ", self.avail_res2
#        print "32 bit res = ", self.avail_res3
        
        self.res_combo = GtkCombo ()
        self.res_combo.set_popdown_strings (res_list)
        self.res_combo.list.connect ("select-child", self.res_cb)
        vbox2.pack_start (self.res_combo, TRUE, FALSE, 10)
#        frame2.add (self.res_combo)


        box.pack_start (hbox1)
        box.pack_start (hbox2, FALSE, TRUE, 10)



#        frame3 = GtkFrame (_("Default Desktop"))
#        hbox3.pack_start (frame3, TRUE, FALSE, 10)

#        self.hbox4 = GtkHBox ()
#        frame3.add (self.hbox4)

#        vbox3 = GtkVBox()
#        self.vbox4 = GtkVBox()


        #--If both KDE and GNOME are selected
        if ((self.todo.hdList.has_key('gnome-core')
             and self.todo.hdList['gnome-core'].selected)
            and (self.todo.hdList.has_key('kdebase')
                 and self.todo.hdList['kdebase'].selected)):

            frame3 = GtkFrame (_("Default Desktop"))
            hbox3.pack_start (frame3, TRUE, FALSE, 10)

            self.hbox4 = GtkHBox ()
            frame3.add (self.hbox4)

            vbox3 = GtkVBox()
            self.vbox4 = GtkVBox()

            gnome_radio = GtkRadioButton (None, (_("GNOME")))
            gnome_radio.connect ("clicked", self.desktop_cb, "GNOME")        
            vbox3.pack_start (gnome_radio, TRUE, FALSE, 10)

            im = self.ics.readPixmap ("gnome.png")
            if im:
                im.render ()
                pix = im.make_pixmap ()
                a = GtkAlignment ()
                a.add (pix)
                a.set (0.5, 0.5, 1.0, 1.0)
                self.vbox4.pack_start (a, TRUE, TRUE)

            kde_radio = GtkRadioButton(gnome_radio, (_("KDE")))
            kde_radio.connect ("clicked", self.desktop_cb, "KDE")
            
            vbox3.pack_start (kde_radio, TRUE, FALSE, 10)

            self.hbox4.pack_start (vbox3)
            self.hbox4.pack_start (self.vbox4)
            box.pack_start (hbox3, FALSE, TRUE, 10)
            
        elif (self.todo.hdList.has_key('gnome-core')
             and self.todo.hdList['gnome-core'].selected):
            
            frame3 = GtkFrame (_("Default Desktop"))
            hbox3.pack_start (frame3, TRUE, FALSE, 10)

            self.hbox4 = GtkHBox ()
            frame3.add (self.hbox4)

            vbox3 = GtkVBox()
            self.vbox4 = GtkVBox()

            gnome_radio = GtkRadioButton (None, (_("GNOME")))
            vbox3.pack_start (gnome_radio, TRUE, FALSE, 10)

            im = self.ics.readPixmap ("gnome.png")
            if im:
                im.render ()
                pix = im.make_pixmap ()
                a = GtkAlignment ()
                a.add (pix)
                a.set (0.5, 0.5, 1.0, 1.0)
                self.vbox4.pack_start (a, TRUE, TRUE)

            self.hbox4.pack_start (vbox3)
            self.hbox4.pack_start (self.vbox4)
            box.pack_start (hbox3, FALSE, TRUE, 10)
            
        elif (self.todo.hdList.has_key('kdebase')
                 and self.todo.hdList['kdebase'].selected):

            
            frame3 = GtkFrame (_("Default Desktop"))
            hbox3.pack_start (frame3, TRUE, FALSE, 10)

            self.hbox4 = GtkHBox ()
            frame3.add (self.hbox4)

            vbox3 = GtkVBox()
            self.vbox4 = GtkVBox()

            kde_radio = GtkRadioButton(None, (_("KDE")))
            vbox3.pack_start (kde_radio, TRUE, FALSE, 10)

            im = self.ics.readPixmap ("kde.png")
            if im:
                im.render ()
                pix = im.make_pixmap ()
                a = GtkAlignment ()
                a.add (pix)
                a.set (0.5, 0.5, 1.0, 1.0)
                self.vbox4.pack_start (a, TRUE, TRUE)


            self.hbox4.pack_start (vbox3)
            self.hbox4.pack_start (self.vbox4)
            box.pack_start (hbox3, FALSE, TRUE, 10)
        else:
            pass

#        box.pack_start (hbox1)
#        box.pack_start (hbox2, FALSE, TRUE, 10)
#        box.pack_start (hbox3, FALSE, TRUE, 10)


        


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
#            hbox.pack_start (vbox)

        
        test = GtkAlignment ()
        button = GtkButton (_("Test this configuration"))
        button.connect ("clicked", self.testPressed)
        test.add (button)
        
#        box.pack_start (hbox, FALSE)
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
        print "Inside getNext"

        print self.hEntry.get_text ()
        print self.vEntry.get_text ()
        
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

        #--If we have never probed before, then probe.  Otherwise, skip it.
        if self.todo.probedFlag == "":
            self.todo.x.probe ()
            self.todo.probedFlag = "TRUE"
        else:
            self.todo.probedFlag = "TRUE"
            
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


        print self.todo.x.monHoriz
        print self.todo.x.monVert

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
        
#        self.videoCard = ""
#        self.videoRam = ""
#        self.didTest = 0
#        self.videoCardState = ""

    def getNext (self):
#        print "Inside getNext"

#        original_parent_node, cardname2 = self.ctree.node_get_row_data(self.todo.videoCardOriginalNode)
#        print "self.videoCardOriginalNode : ", original_parent_node , " - ", cardname2
#        self.todo.videoCardOriginalNode = ""
#        self.todo.videoCardRamState = 

        
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
            #	    if self.custom.get_active () and not self.skip.get_active ():
            if not self.skip.get_active ():
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

        count = 0

        for sizes in ("256k", "512k", "1024k", "2048k", "4096k",
                     "8192k", "16384k", "32768k"):     
            if size == sizes:
                self.todo.videoRamState = count
            count = count + 1

    def movetree (self, ctree, area, selected_node):
        self.ctree.freeze()
        self.ctree.select(self.selected_node)
        parent_node, cardname = self.ctree.node_get_row_data(self.selected_node)                        
        self.ctree.expand(parent_node)
#        print self.selected_node
        self.ctree.node_moveto(self.selected_node, 0, 0.5, 0)
        self.ctree.thaw()

    def movetree2 (self, ctree, area, node):
        self.ctree.freeze()
        node = self.todo.videoCardOriginalNode
        current_parent_node, cardname2 = self.ctree.node_get_row_data(self.todo.videoCardOriginalNode)

        self.selected_node = node
        self.ctree.select(node)
        parent_node, cardname = self.ctree.node_get_row_data(node)                        
        self.ctree.expand(node)
        self.ctree.node_moveto(node, 0, 0.5, 0)
        self.ctree.thaw()

    def selectCb_tree (self, ctree, node, column):
#        print "Inside selectCb_tree"
        try:
            self.current_node = node
            parent, cardname = ctree.node_get_row_data (node)
#            print cardname
            if cardname:
                card = self.cards[cardname]
                depth = 0
                while depth < 16 and card.has_key ("SEE"):
                    card = self.cards[card["SEE"]]
                    depth = depth + 1
#                print card
                self.todo.x.setVidcard (card)
        except:
            pass
            
    def restorePressed (self, ramMenu):
        try:
            current_parent_node, cardname1 = self.ctree.node_get_row_data(self.current_node)
            original_parent_node, cardname2 = self.ctree.node_get_row_data(self.todo.videoCardOriginalNode)

            #        data = self.todo.videoCardOriginalName

            #        print "self.current_node : ", current_parent_node , " - ", cardname1
            #        print "self.videoCardOriginalNode : ", original_parent_node , " - ", cardname2

            if current_parent_node != original_parent_node:
                self.ctree.collapse(current_parent_node)

            if cardname1 != cardname2:
                self.movetree2(self.ctree, self.todo.videoCardOriginalNode, 0)
            else:
                #            print "Cardnames are equal...don't do anything"
                pass

        except:
            pass
        
        self.todo.videoRamState = self.default_ram
        self.ramOption.remove_menu ()
        self.ramMenu.set_active(self.default_ram)
        self.ramOption.set_menu (self.ramMenu)

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
            self.ctree = GtkCTree ()
            self.ctree.set_selection_mode (SELECTION_BROWSE)
            self.ctree.set_expander_style(CTREE_EXPANDER_TRIANGLE)
            self.ctree.set_line_style(CTREE_LINES_NONE)

            self.videocard_p, self.videocard_b = create_pixmap_from_xpm_d (self.ctree, None, xpms_gui.VIDEOCARD_XPM)

            manufacturer = ["AOpen", "ASUS", "ATI", "Actix", "Ark Logic", "Avance Logic", "Compaq",
                            "Canopus", "Cardex", "Chaintech", "Chips & Technologies", "Cirrus", "Creative Labs",
                            "DFI", "DSV", "DataExpert", "Dell", "Diamond", "Digital", "ELSA", "EONtronics",
                            "Epson", "ExpertColor", "Gainward", "Generic", "Genoa", "Hercules", "Intel",
                            "Jaton", "LeadTek", "MELCO", "MachSpeed", "Matrox", "Miro", "NVIDIA", "NeoMagic",
                            "Number Nine", "Oak", "Octek", "Orchid", "Paradise", "PixelView", "Quantum",
                            "RIVA", "Real3D", "Rendition", "S3", "Sharp", "SMI", "SNI", "SPEA", "STB", "SiS",
                            "Sierra", "Sigma", "Soyo", "Spider", "Sun", "TechWorks", "Toshiba", "Trident",
                            "VideoLogic", "ViewTop", "Voodoo", "WD", "WinFast"]     

                
            aopen = self.ctree.insert_node (None, None, ("AOpen",), 2, self.videocard_p, self.videocard_b,
                                        self.videocard_p, self.videocard_b, FALSE)
            asus = self.ctree.insert_node (None, None, ("ASUS ",), 2, self.videocard_p, self.videocard_b,
                                        self.videocard_p, self.videocard_b, FALSE)
            ati = self.ctree.insert_node (None, None, ("ATI",), 2, self.videocard_p, self.videocard_b,
                                        self.videocard_p, self.videocard_b, FALSE)
            actix = self.ctree.insert_node (None, None, ("Actix ",), 2, self.videocard_p, self.videocard_b,
                                        self.videocard_p, self.videocard_b, FALSE)
            arklogic = self.ctree.insert_node (None, None, ("Ark Logic ",), 2, self.videocard_p, self.videocard_b,
                                        self.videocard_p, self.videocard_b, FALSE)
            avancelogic = self.ctree.insert_node (None, None, ("Avance Logic ",), 2, self.videocard_p, self.videocard_b,
                                        self.videocard_p, self.videocard_b, FALSE)
            compaq = self.ctree.insert_node (None, None, ("Compaq",), 2, self.videocard_p, self.videocard_b,
                                        self.videocard_p, self.videocard_b, FALSE)
            canopus = self.ctree.insert_node (None, None, ("Canopus",), 2, self.videocard_p, self.videocard_b,
                                         self.videocard_p, self.videocard_b, FALSE)
            cardex = self.ctree.insert_node (None, None, ("Cardex",), 2, self.videocard_p, self.videocard_b,
                                        self.videocard_p, self.videocard_b, FALSE)
            chaintech = self.ctree.insert_node (None, None, ("Chaintech",), 2, self.videocard_p, self.videocard_b,
                                           self.videocard_p, self.videocard_b, FALSE)
            cnt = self.ctree.insert_node (None, None, ("Chips & Technologies",), 2, self.videocard_p, self.videocard_b,
                                     self.videocard_p, self.videocard_b, FALSE)
            cirrus = self.ctree.insert_node (None, None, ("Cirrus",), 2, self.videocard_p, self.videocard_b,
                                        self.videocard_p, self.videocard_b, FALSE)
            creativelabs = self.ctree.insert_node (None, None, ("Creative Labs",), 2, self.videocard_p, self.videocard_b,
                                              self.videocard_p, self.videocard_b, FALSE)
            dfi = self.ctree.insert_node (None, None, ("DFI",), 2, self.videocard_p, self.videocard_b,
                                     self.videocard_p, self.videocard_b, FALSE)
            dsv = self.ctree.insert_node (None, None, ("DSV",), 2, self.videocard_p, self.videocard_b,
                                     self.videocard_p, self.videocard_b, FALSE)
            dataexpert = self.ctree.insert_node (None, None, ("Data Expert",), 2, self.videocard_p, self.videocard_b,
                                            self.videocard_p, self.videocard_b, FALSE)
            dell = self.ctree.insert_node (None, None, ("Dell",), 2, self.videocard_p, self.videocard_b,
                                      self.videocard_p, self.videocard_b, FALSE)
            diamond = self.ctree.insert_node (None, None, ("Diamond",), 2, self.videocard_p, self.videocard_b,
                                         self.videocard_p, self.videocard_b, FALSE)
            digital = self.ctree.insert_node (None, None, ("Digital",), 2, self.videocard_p, self.videocard_b,
                                         self.videocard_p, self.videocard_b, FALSE)
            elsa = self.ctree.insert_node (None, None, ("ELSA",), 2, self.videocard_p, self.videocard_b,
                                      self.videocard_p, self.videocard_b, FALSE)
            eontronics = self.ctree.insert_node (None, None, ("EONtronics",), 2, self.videocard_p, self.videocard_b,
                                            self.videocard_p, self.videocard_b, FALSE)
            epson = self.ctree.insert_node (None, None, ("Epson",), 2, self.videocard_p, self.videocard_b,
                                       self.videocard_p, self.videocard_b, FALSE)
            expertcolor = self.ctree.insert_node (None, None, ("ExpertColor",), 2, self.videocard_p, self.videocard_b,
                                             self.videocard_p, self.videocard_b, FALSE)
            gainward = self.ctree.insert_node (None, None, ("Gainward",), 2, self.videocard_p, self.videocard_b,
                                          self.videocard_p, self.videocard_b, FALSE)
            generic = self.ctree.insert_node (None, None, ("Generic",), 2, self.videocard_p, self.videocard_b,
                                         self.videocard_p, self.videocard_b, FALSE)
            genoa = self.ctree.insert_node (None, None, ("Genoa",), 2, self.videocard_p, self.videocard_b,
                                       self.videocard_p, self.videocard_b, FALSE)
            hercules = self.ctree.insert_node (None, None, ("Hercules",), 2, self.videocard_p, self.videocard_b,
                                          self.videocard_p, self.videocard_b, FALSE)
            intel = self.ctree.insert_node (None, None, ("Intel",), 2, self.videocard_p, self.videocard_b,
                                       self.videocard_p, self.videocard_b, FALSE)
            jaton = self.ctree.insert_node (None, None, ("Jaton",), 2, self.videocard_p, self.videocard_b,
                                       self.videocard_p, self.videocard_b, FALSE)
            leadtek = self.ctree.insert_node (None, None, ("LeadTek",), 2, self.videocard_p, self.videocard_b,
                                         self.videocard_p, self.videocard_b, FALSE)
            melco = self.ctree.insert_node (None, None, ("MELCO",), 2, self.videocard_p, self.videocard_b,
                                       self.videocard_p, self.videocard_b, FALSE)
            machspeed = self.ctree.insert_node (None, None, ("MachSpeed",), 2, self.videocard_p, self.videocard_b,
                                           self.videocard_p, self.videocard_b, FALSE)
            matrox = self.ctree.insert_node (None, None, ("Matrox",), 2, self.videocard_p, self.videocard_b,
                                        self.videocard_p, self.videocard_b, FALSE)
            miro = self.ctree.insert_node (None, None, ("Miro",), 2, self.videocard_p, self.videocard_b,
                                      self.videocard_p, self.videocard_b, FALSE)
            nvidia = self.ctree.insert_node (None, None, ("NVIDIA",), 2, self.videocard_p, self.videocard_b,
                                        self.videocard_p, self.videocard_b, FALSE)
            neomagic = self.ctree.insert_node (None, None, ("NeoMagic",), 2, self.videocard_p, self.videocard_b,
                                          self.videocard_p, self.videocard_b, FALSE)
            numbernine = self.ctree.insert_node (None, None, ("Number Nine",), 2, self.videocard_p, self.videocard_b,
                                            self.videocard_p, self.videocard_b, FALSE)
            oak = self.ctree.insert_node (None, None, ("Oak",), 2, self.videocard_p, self.videocard_b,
                                     self.videocard_p, self.videocard_b, FALSE)
            octek = self.ctree.insert_node (None, None, ("Octek",), 2, self.videocard_p, self.videocard_b,
                                       self.videocard_p, self.videocard_b, FALSE)
            orchid = self.ctree.insert_node (None, None, ("Orchid",), 2, self.videocard_p, self.videocard_b,
                                        self.videocard_p, self.videocard_b, FALSE)
            other = self.ctree.insert_node (None, None, ("Other",), 2, self.videocard_p, self.videocard_b,
                                        self.videocard_p, self.videocard_b, FALSE)
            paradise = self.ctree.insert_node (None, None, ("Paradise",), 2, self.videocard_p, self.videocard_b,
                                          self.videocard_p, self.videocard_b, FALSE)
            pixelview = self.ctree.insert_node (None, None, ("PixelView",), 2, self.videocard_p, self.videocard_b,
                                           self.videocard_p, self.videocard_b, FALSE)
            quantum = self.ctree.insert_node (None, None, ("Quantum",), 2, self.videocard_p, self.videocard_b,
                                         self.videocard_p, self.videocard_b, FALSE)
            riva = self.ctree.insert_node (None, None, ("RIVA",), 2, self.videocard_p, self.videocard_b,
                                      self.videocard_p, self.videocard_b, FALSE)
            real3D = self.ctree.insert_node (None, None, ("Real3D",), 2, self.videocard_p, self.videocard_b,
                                        self.videocard_p, self.videocard_b, FALSE)
            rendition = self.ctree.insert_node (None, None, ("Rendition",), 2, self.videocard_p, self.videocard_b,
                                           self.videocard_p, self.videocard_b, FALSE)
            s3 = self.ctree.insert_node (None, None, ("S3",), 2, self.videocard_p, self.videocard_b,
                                    self.videocard_p, self.videocard_b, FALSE)
            sharp = self.ctree.insert_node (None, None, ("Sharp",), 2, self.videocard_p, self.videocard_b,
                                       self.videocard_p, self.videocard_b, FALSE)
            smi = self.ctree.insert_node (None, None, ("SMI",), 2, self.videocard_p, self.videocard_b,
                                     self.videocard_p, self.videocard_b, FALSE)
            sni = self.ctree.insert_node (None, None, ("SNI",), 2, self.videocard_p, self.videocard_b,
                                     self.videocard_p, self.videocard_b, FALSE)
            spea = self.ctree.insert_node (None, None, ("SPEA",), 2, self.videocard_p, self.videocard_b,
                                      self.videocard_p, self.videocard_b, FALSE)
            stb = self.ctree.insert_node (None, None, ("STB",), 2, self.videocard_p, self.videocard_b,
                                     self.videocard_p, self.videocard_b, FALSE)
            sis = self.ctree.insert_node (None, None, ("SiS",), 2, self.videocard_p, self.videocard_b,
                                     self.videocard_p, self.videocard_b, FALSE)
            sierra = self.ctree.insert_node (None, None, ("Sierra",), 2, self.videocard_p, self.videocard_b,
                                        self.videocard_p, self.videocard_b, FALSE)
            sigma = self.ctree.insert_node (None, None, ("Sigma",), 2, self.videocard_p, self.videocard_b,
                                       self.videocard_p, self.videocard_b, FALSE)
            soyo = self.ctree.insert_node (None, None, ("Soyo",), 2, self.videocard_p, self.videocard_b,
                                      self.videocard_p, self.videocard_b, FALSE)
            spider = self.ctree.insert_node (None, None, ("Spider",), 2, self.videocard_p, self.videocard_b,
                                        self.videocard_p, self.videocard_b, FALSE)
            sun = self.ctree.insert_node (None, None, ("Sun",), 2, self.videocard_p, self.videocard_b,
                                     self.videocard_p, self.videocard_b, FALSE)
            techworks = self.ctree.insert_node (None, None, ("TechWorks",), 2, self.videocard_p, self.videocard_b,
                                           self.videocard_p, self.videocard_b, FALSE)
            toshiba = self.ctree.insert_node (None, None, ("Toshiba",), 2, self.videocard_p, self.videocard_b,
                                         self.videocard_p, self.videocard_b, FALSE)
            trident = self.ctree.insert_node (None, None, ("Trident",), 2, self.videocard_p, self.videocard_b,
                                         self.videocard_p, self.videocard_b, FALSE)
            videologic = self.ctree.insert_node (None, None, ("VideoLogic",), 2, self.videocard_p, self.videocard_b,
                                            self.videocard_p, self.videocard_b, FALSE)
            viewtop = self.ctree.insert_node (None, None, ("ViewTop",), 2, self.videocard_p, self.videocard_b,
                                         self.videocard_p, self.videocard_b, FALSE)
            voodoo = self.ctree.insert_node (None, None, ("Voodoo",), 2, self.videocard_p, self.videocard_b,
                                        self.videocard_p, self.videocard_b, FALSE)
            wd = self.ctree.insert_node (None, None, ("WD",), 2, self.videocard_p, self.videocard_b,
                                    self.videocard_p, self.videocard_b, FALSE)
            winfast = self.ctree.insert_node (None, None, ("WinFast",), 2, self.videocard_p, self.videocard_b,
                                         self.videocard_p, self.videocard_b, FALSE)



#            self.cardList = GtkCList ()
#            self.cardList.set_selection_mode (SELECTION_BROWSE)
#            self.cardList.connect ("select_row", self.selectCb)




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
                    node = self.ctree.insert_node (aopen, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (aopen, card))
#                    print card
                elif temp[:4] == "asus":
                    node = self.ctree.insert_node (asus, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (asus, card))
                elif temp[:3] == "ati":
                    node = self.ctree.insert_node (ati, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (ati, card))
                elif temp[:5] == "actix":
                    node = self.ctree.insert_node (actix, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (actix, card))
                elif temp[:9] == "ark logic":
                    node = self.ctree.insert_node (arklogic, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (arklogic, card))
                elif temp[:12] == "avance logic":
                    node = self.ctree.insert_node (avancelogic, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (avancelogic, card))
                elif temp[:6] == "compaq":
                    node = self.ctree.insert_node (compaq, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (compaq, card))
                elif temp[:7] == "canopus":
                    node = self.ctree.insert_node (canopus, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (canopus, card))
                elif temp[:6] == "cardex":
                    node = self.ctree.insert_node (cardex, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (cardex, card))
                elif temp[:9] == "chaintech":
                    node = self.ctree.insert_node (chaintech, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (chaintech, card))
                elif temp[:5] == "chips":
                    node = self.ctree.insert_node (cnt, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (cnt, card))
                elif temp[:6] == "cirrus":
                    node = self.ctree.insert_node (cirrus, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (cirrus, card))
                elif temp[:8] == "creative":
                    node = self.ctree.insert_node (creativelabs, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (creativelabs, card))
                elif temp[:3] == "dfi":
                    node = self.ctree.insert_node (dfi, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (dfi, card))
                elif temp[:3] == "dsv":
                    node = self.ctree.insert_node (dsv, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (dsv, card))
                elif temp[:4] == "data":
                    node = self.ctree.insert_node (dataexpert, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (dataexpert, card))
                elif temp[:4] == "dell":
                    node = self.ctree.insert_node (dell, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (dell, card))
                elif temp[:7] == "diamond":
                    node = self.ctree.insert_node (diamond, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (diamond, card))
                elif temp[:7] == "digital":
                    node = self.ctree.insert_node (digital, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (digital, card))
                elif temp[:4] == "elsa":
                    node = self.ctree.insert_node (elsa, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (elsa, card))
                elif temp[:10] == "eontronics":
                    node = self.ctree.insert_node (eontronics, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (eontronics, card))
                elif temp[:5] == "epson":
                    node = self.ctree.insert_node (epson, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (epson, card))
                elif temp[:11] == "expertcolor":
                    node = self.ctree.insert_node (expertcolor, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (expertcolor, card))
                elif temp[:8] == "gainward":
                    node = self.ctree.insert_node (gainward, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (gainward, card))
                elif temp[:7] == "generic":
                    node = self.ctree.insert_node (generic, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (generic, card))
                elif temp[:5] == "genoa":
                    node = self.ctree.insert_node (genoa, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (genoa, card))
                elif temp[:8] == "hercules":
                    node = self.ctree.insert_node (hercules, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (hercules, card))
                elif temp[:5] == "intel":
                    node = self.ctree.insert_node (intel, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (intel, card))
                elif temp[:5] == "jaton":
                    node = self.ctree.insert_node (jaton, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (jaton, card))
                elif temp[:7] == "leadtek":
                    node = self.ctree.insert_node (leadtek, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (leadtek, card))
                elif temp[:5] == "melco":
                    node = self.ctree.insert_node (melco, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (melco, card))
                elif temp[:9] == "machspeed":
                    node = self.ctree.insert_node (machspeed, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (machspeed, card))
                elif temp[:6] == "matrox":
                    node = self.ctree.insert_node (matrox, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (matrox, card))
                elif temp[:4] == "miro":
                    node = self.ctree.insert_node (miro, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (miro, card))
                elif temp[:6] == "nvidia":
                    node = self.ctree.insert_node (nvidia, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (nvidia, card))
                elif temp[:8] == "neomagic":
                    node = self.ctree.insert_node (neomagic, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (neomagic, card))
                elif temp[:6] == "number":
                    node = self.ctree.insert_node (numbernine, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (numbernine, card))
                elif temp[:3] == "oak":
                    node = self.ctree.insert_node (oak, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (oak, card))
                elif temp[:5] == "octek":
                    node = self.ctree.insert_node (octek, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (octek, card))
                elif temp[:6] == "orchid":
                    node = self.ctree.insert_node (orchid, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (orchid, card))
                elif temp[:8] == "paradise":
                    node = self.ctree.insert_node (paradise, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (paradise, card))
                elif temp[:9] == "pixelview":
                    node = self.ctree.insert_node (pixelview, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (pixelview, card))
                elif temp[:7] == "quantum":
                    node = self.ctree.insert_node (quantum, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (quantum, card))
                elif temp[:4] == "riva":
                    node = self.ctree.insert_node (riva, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (riva, card))
                elif temp[:6] == "real3d":
                    node = self.ctree.insert_node (real3D, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (real3D, card))
                elif temp[:9] == "rendition":
                    node = self.ctree.insert_node (rendition, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (rendition, card))
                elif temp[:2] == "s3":
                    node = self.ctree.insert_node (s3, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (s3, card))
                elif temp[:5] == "sharp":
                    node = self.ctree.insert_node (sharp, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (sharp, card))
                elif temp[:3] == "smi":
                    node = self.ctree.insert_node (smi, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (smi, card))
                elif temp[:3] == "sni":
                    node = self.ctree.insert_node (sni, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (sni, card))
                elif temp[:4] == "spea":
                    node = self.ctree.insert_node (spea, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (spea, card))
                elif temp[:3] == "stb":
                    node = self.ctree.insert_node (stb, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (stb, card))
                elif temp[:3] == "sis":
                    node = self.ctree.insert_node (sis, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (sis, card))
                elif temp[:6] == "sierra":
                    node = self.ctree.insert_node (sierra, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (sierra, card))
                elif temp[:5] == "sigma":
                    node = self.ctree.insert_node (sigma, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (sigma, card))
                elif temp[:4] == "soyo":
                    node = self.ctree.insert_node (soyo, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (soyo, card))
                elif temp[:6] == "spider":
                    node = self.ctree.insert_node (spider, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (spider, card))
                elif temp[:3] == "sun":
                    node = self.ctree.insert_node (sun, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (sun, card))
                elif temp[:9] == "techworks":
                    node = self.ctree.insert_node (techworks, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (techworks, card))
                elif temp[:7] == "toshiba":
                    node = self.ctree.insert_node (toshiba, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (toshiba, card))
                elif temp[:7] == "trident":
                    node = self.ctree.insert_node (trident, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (trident, card))
                elif temp[:10] == "videologic":
                    node = self.ctree.insert_node (videologic, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (videologic, card))
                elif temp[:7] == "viewtop":
                    node = self.ctree.insert_node (viewtop, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (viewtop, card))
                elif temp[:6] == "voodoo":
                    node = self.ctree.insert_node (voodoo, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (voodoo, card))
                elif temp[:2] == "wd":
                    node = self.ctree.insert_node (wd, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (wd, card))
                elif temp[:7] == "winfast":
                    node = self.ctree.insert_node (winfast, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (winfast, card))
                else:
                    node = self.ctree.insert_node (other, None, (card,), 2)
                    self.ctree.node_set_row_data(node, (other, card))

                if self.todo.videoCardOriginalName != "":
                    if card == self.todo.videoCardOriginalName:
                        self.todo.videoCardOriginalNode = node

                if self.todo.x.vidCards:
                    if card == self.todo.x.vidCards[self.todo.x.primary]["NAME"]:
#                        print card
                        #--If we haven't been to this screen before, initialize the state to the original value
                        if self.todo.videoCardOriginalName == "":
                            self.todo.videoCardOriginalName = card
                            self.todo.videoCardOriginalNode = node

                        self.current_node = node
                        self.selected_node = node

                    elif card == self.todo.videoCardOriginalName:
                        card = self.todo.videoCardOriginalName
                        self.todo.videoCardOriginalNode = node
#                        self.current_node = node
#                        self.selected_node = node

                else:
                    if card == "Generic VGA compatible":
                        #--If we haven't been to this screen before, initialize the state to the original value
                        if self.todo.videoCardOriginalName == "":
                            self.todo.videoCardOriginalName = card
                            self.todo.videoCardOriginalNode = node

                        self.current_node = node
                        self.selected_node = node
                    
#            for card in cards:
#                row = self.cardList.append ((card,))
#                self.cardList.set_row_data (row, card)
#                print "Row = ", row
#                print "Card = ", card
#                if self.todo.x.vidCards:
#                    if card == self.todo.x.vidCards[self.todo.x.primary]["NAME"]:
#                        select = row
#                else:
#                    if card == "Generic VGA compatible":
#                        select = row

            #- Once ctree is realized, then expand necessary branch and select selected item.
            self.ctree.connect ("tree_select_row", self.selectCb_tree)
            self.ctree.connect ("draw", self.movetree, self.selected_node)

#            self.cardList.connect ("draw", self.moveto, select)
            sw = GtkScrolledWindow ()
#            sw.add (self.cardList)
            sw.add (self.ctree)
            box.pack_start (sw, TRUE)




            #Memory configuration menu
            hbox = GtkHBox()
            hbox.set_border_width(3)
            
            label = GtkLabel (_("Video card RAM: "))

            self.ramOption = GtkOptionMenu()
            self.ramOption.set_usize (40, 20)
            self.ramMenu = GtkMenu()

            mem1 = GtkMenuItem("256 kB")
            mem1.connect ("activate", self.memory_cb, "256k")
            mem2 = GtkMenuItem("512 kB")
            mem2.connect ("activate", self.memory_cb, "512k")
            mem3 = GtkMenuItem("1 MB")
            mem3.connect ("activate", self.memory_cb, "1024k")
            mem4 = GtkMenuItem("2 MB")
            mem4.connect ("activate", self.memory_cb, "2048k")
            mem5 = GtkMenuItem("4 MB")
            mem5.connect ("activate", self.memory_cb, "4096k")
            mem6 = GtkMenuItem("8 MB")
            mem6.connect ("activate", self.memory_cb, "8192k")
            mem7 = GtkMenuItem("16 MB")
            mem7.connect ("activate", self.memory_cb, "16384k")
            mem8 = GtkMenuItem("32 MB")
            mem8.connect ("activate", self.memory_cb, "32768k")
            self.ramMenu.add(mem1)
            self.ramMenu.add(mem2)
            self.ramMenu.add(mem3)
            self.ramMenu.add(mem4)
            self.ramMenu.add(mem5)
            self.ramMenu.add(mem6)
            self.ramMenu.add(mem7)
            self.ramMenu.add(mem8)

            self.default_ram = 0
            count = 0

            for size in ("256k", "512k", "1024k", "2048k", "4096k",
                         "8192k", "16384k", "32768k"):
                if size[:-1] == self.todo.x.vidRam:
                    if self.todo.videoRamState == "":          
                        self.todo.videoRamState = count
                        self.ramMenu.set_active(count)
                    else:                        
                        self.ramMenu.set_active(self.todo.videoRamState)                    
                    self.default_ram = count
                count = count + 1

            hbox.pack_start(label, FALSE)
            hbox.pack_start(self.ramOption, TRUE, TRUE, 25)

            self.ramOption.set_menu (self.ramMenu)
            box.pack_start (hbox, FALSE)

                
            # Memory configuration table
            table = GtkTable()
            group = None
            count = 0
            for size in ("256k", "512k", "1024k", "2048k", "4096k",
                         "8192k", "16384k", "32768k"):
                button = GtkRadioButton (group, size)
#                button.connect ('clicked', self.memory_cb, size)
                if size[:-1] == self.todo.x.vidRam:
                    button.set_active (1)
                if not group:
                    group = button
                table.attach (button, count % 4, (count % 4) + 1,
                              count / 4, (count / 4) + 1)
                count = count + 1
#            box.pack_start (table, FALSE)
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

#            hbox = GtkHBox ()

            buttonBox = GtkHButtonBox ()
            buttonBox.set_layout (BUTTONBOX_EDGE)
#            buttonBox.pack_start (button)

            restore = GtkButton (_("Restore original values"))
            restore.connect ("clicked", self.restorePressed)
#            buttonBox.pack_start (restore)
            hbox.pack_start(restore, FALSE, 25)



#            test.add (button)
#            test.add (restore)
            test.add (buttonBox)

#            box.pack_start (hbox, FALSE) 
            box.pack_start (test, FALSE)

            self.custom = GtkCheckButton (_("Customize X Configuration"))
            self.custom.connect ("toggled", self.customToggled)
#            optbox.pack_start (self.custom, FALSE)

        self.xdm = GtkCheckButton (_("Use Graphical Login"))
        self.skip = GtkCheckButton (_("Skip X Configuration"))
        self.skip.connect ("toggled", self.skipToggled) 

#        optbox.pack_start (self.xdm, FALSE)

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

#        box.pack_start (hbox, FALSE)

        self.topbox = GtkVBox (FALSE, 5)
        self.topbox.set_border_width (5)
        self.topbox.pack_start (box, TRUE, TRUE)
        self.topbox.pack_start (self.skip, FALSE)

        self.configbox = box

        self.skip.set_active (self.todo.x.skip)

        return self.topbox
