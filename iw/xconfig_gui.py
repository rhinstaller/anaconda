#
# xconfig_gui: gui X configuration
#
# Brent Fox <bfox@redhat.com>
#
# Copyright 2001 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import copy
import string
import sys
import iutil
import glob
import gui
import gtk
from iw_gui import *
from translate import _, N_
from monitor import isValidSyncRange
from videocard import Videocard_blacklist

class XCustomWindow (InstallWindow):

    htmlTag = "xcustom"
    windowTitle = N_("Customize Graphics Configuration")

    def __init__ (self, ics):
        InstallWindow.__init__ (self, ics)
        self.ics.setNextEnabled (gtk.TRUE)
        
    def getNext (self):
        newmodes = {}
        newmodes[self.selectedDepth] = []
        newmodes[self.selectedDepth].append (self.selectedRes)

        self.xconfig.setManualModes(newmodes)
        
        self.desktop.setDefaultDesktop (self.newDesktop)

        if self.text.get_active ():
            rl = 3
        elif self.graphical.get_active ():
            rl = 5

        self.desktop.setDefaultRunLevel(rl)
        
    def testPressed (self, widget, *args):
        newmodes = {}
        newmodes[self.selectedDepth] = []
        newmodes[self.selectedDepth].append (self.selectedRes)

        manmodes = self.xconfig.getManualModes()
        self.xconfig.setManualModes(newmodes)

        try:
            self.xconfig.test (root="/mnt/sysimage/")
        except RuntimeError:
            ### test failed window
            pass

        self.xconfig.setManualModes(manmodes)

    def numCompare (self, first, second):
        first = string.atoi (first)
        second = string.atoi (second)
        if first > second:
            return 1
        elif first < second:
            return -1
        return 0

    def depth_cb (self, widget, data):
        depth = self.depth_combo.list.child_position (data)
        if self.selectedDepth == self.bit_depth[depth]:
            return
        self.selectedDepth = self.bit_depth[depth]
        curres = self.selectedRes
        newmodes = self.xconfig.availableModes()[self.selectedDepth]
        self.res_combo.set_popdown_strings(newmodes)
        if curres in newmodes:
            self.res_combo.list.select_item(newmodes.index(curres))
        
    def res_cb (self, widget, data):
        newres = self.res_combo.list.child_position (data)
        if self.currentRes == newres:
            return
        
        self.currentRes = self.res_combo.list.child_position (data)
        self.selectedRes = self.res_list[self.currentRes]
        self.swap_monitor (self.currentRes)

    def load_monitor_preview_pixmap(self, file):
        if self.monitor_align:
            self.hbox.remove (self.monitor_align)

        pix = self.ics.readPixmap (file)
        if pix:
            self.monitor_align = gtk.Alignment ()
            self.monitor_align.add (pix)
            self.monitor_align.set (0.5, 0.5, 1.0, 1.0)
            self.hbox.pack_start (self.monitor_align, gtk.TRUE, gtk.TRUE)
        self.hbox.show_all()

    def swap_monitor (self, num):
        def find_monitor_pixmaps():
            files = []
                
            pixmaps1 = glob.glob("/usr/share/anaconda/pixmaps/monitor_*")
            pixmaps2 = glob.glob("pixmaps/monitor_*")
            if len(pixmaps1) < len(pixmaps2):
                files = pixmaps2
            else:
                files = pixmaps1

            pixmaps = []
            for pixmap in files:
                pixmaps.append(pixmap[string.find(pixmap, "monitor_"):])
                
            pixmaps.sort()
            return pixmaps

        if self.monitor_pixmaps == None:
            self.monitor_pixmaps = find_monitor_pixmaps()

        self.load_monitor_preview_pixmap(self.monitor_pixmaps[num])

    def display_desktop_pixmap(self, desktop):
        self.vbox4.destroy ()
        self.vbox4 = gtk.VBox ()

        if desktop == "GNOME":
           pix = self.ics.readPixmap("gnome.png")
        elif desktop == "KDE":
            pix = self.ics.readPixmap("kde.png")
        else:
            pix = None

        if pix:
            a = gtk.Alignment ()
            a.add (pix)
            a.set (0.5, 0.5, 1.0, 1.0)
            self.vbox4.pack_start (a, gtk.TRUE, gtk.TRUE)

        self.hbox4.pack_start (self.vbox4)
        self.hbox4.show_all ()

    def desktop_cb (self, widget, desktop):
        self.newDesktop = desktop

        self.display_desktop_pixmap(desktop)

    # XCustomWindow tag="xcustom"
    def getScreen (self, xconfig, monitor, videocard, desktop, comps):

        self.xconfig = xconfig
        self.monitor = monitor
        self.videocard = videocard
        self.desktop = desktop

        # create toplevel packing structure
        self.box = gtk.VBox (gtk.FALSE)
        self.box.set_border_width (5)

        # hbox and alignment used for monitor preview area
        # list of pixmaps for monitor preview
        self.monitor_pixmaps = None
        self.hbox = gtk.HBox (gtk.FALSE, 5)
        self.monitor_align = None
        self.desktop_align = None
        self.load_monitor_preview_pixmap("monitor.png")
        self.box.pack_start (self.hbox)

        # determine video modes available for this card/monitor combo
        available = self.xconfig.availableModes()
        availableDepths = []
        for adepth in available.keys():
            if len(available[adepth]) > 0:
                availableDepths.append(adepth)
        availableDepths.sort(self.numCompare)

        hbox1 = gtk.HBox (gtk.FALSE, 5)
        hbox3 = gtk.HBox (gtk.FALSE, 5)
        hbox4 = gtk.HBox (gtk.FALSE, 5)

        frame1 = gtk.Frame (_("Color Depth:"))
        frame1.set_shadow_type (SHADOW_NONE)
        frame1.set_border_width (10)
        hbox1.pack_start(frame1, gtk.TRUE, gtk.FALSE, 0)

        depth_list = [(_("256 Colors (8 Bit)")), (_("High Color (16 Bit)")), (_("True Color (24 Bit)"))]
        self.bit_depth = ["8", "16", "32"]

        self.avail_depths = depth_list[:len(availableDepths)]
        self.depth_combo = gtk.Combo ()
        self.depth_combo.entry.set_editable (gtk.FALSE)
        self.depth_combo.set_popdown_strings (self.avail_depths)

        frame1.add (self.depth_combo)
        frame2 = gtk.Frame (_("Screen Resolution:"))
        frame2.set_shadow_type (SHADOW_NONE)
        frame2.set_border_width (10)
        hbox1.pack_start (frame2, gtk.TRUE, gtk.FALSE, 2)

        self.res_list = ["640x480", "800x600", "1024x768", "1152x864",
                         "1280x1024", "1400x1050", "1600x1200"]

        self.res_combo = gtk.Combo ()
        self.res_combo.entry.set_editable (gtk.FALSE)

        # determine current selection, or if none exists, pick reasonable
        # defaults.
        #
        # getManualModes() should return a dictionary with one key (depth),
        #                  which has a single corresponding resolution
        #
        manualmodes = self.xconfig.getManualModes()
        if manualmodes:
            self.selectedDepth = manualmodes.keys()[0]
            self.selectedRes = manualmodes[self.selectedDepth][0]
        else:
            self.selectedDepth = None
            self.selectedRes = None

        # if selected depth not acceptable then force it to be at least 8bpp
        if self.selectedDepth and int(self.selectedDepth) < 8:
            self.selectedDepth = "8"

        if not self.selectedDepth or not self.selectedRes:
            if len(available) == 1:
                self.res_combo.set_popdown_strings (available["8"])
                self.selectedDepth = "8"
                self.selectedRes = available[self.selectedDepth][0]
            elif len(available) >= 2:
                #--If they can do 16 bit color, default to 16 bit at 1024x768
                self.depth_combo.list.select_item (1)
                self.selectedDepth = "16"
            
                self.res_combo.set_popdown_strings (available["16"])

                if "1024x768" in available["16"]:
                    self.selectedRes = "1024x768"
                elif "800x600" in available["16"]:
                    self.selectedRes = "800x600"
                else:
                    self.selectedRes = "640x480"
        else:
            self.res_combo.set_popdown_strings (available[self.selectedDepth])

        frame2.add (self.res_combo)

        # apply current configuration to UI
        count = 0
        for depth in self.bit_depth:
            if depth == self.selectedDepth:
                self.depth_combo.list.select_item (count)
                break
            count = count + 1

        count = 0
        self.currentRes = 0
        for res in self.res_list:
            if res == self.selectedRes:
                self.res_combo.list.select_item (count)
                self.currentRes = count
                break
            count = count + 1

        location = available[self.selectedDepth].index(self.selectedRes)
        self.swap_monitor(location)

        self.depth_combo.list.connect ("select-child", self.depth_cb)
        self.res_combo.list.connect ("select-child", self.res_cb)

        self.box.pack_start (hbox1, gtk.FALSE)

        # cannot reliably test on i810 or Voodoo driver, or on Suns who dont
        # need it since they are fixed resolution

        self.cantprobe = not self.videocard.primaryCard().canTestSafely()

        if not self.cantprobe:
            test = gtk.Alignment (.9, 0, 0, 0)
            button = gtk.Button (_("   Test Setting   "))
            button.connect ("clicked", self.testPressed)
            test.add (button)
            self.box.pack_start (test, gtk.FALSE)

        #--If both KDE and GNOME are selected
        if comps:
            gnomeSelected = (comps.packages.has_key('gnome-core')
                             and comps.packages['gnome-core'].selected)
            kdeSelected = (comps.packages.has_key('kdebase')
                           and comps.packages['kdebase'].selected)
        else:
            gnomeSelected = 0
            kdeSelected = 0

        self.newDesktop = ""
        self.origDesktop = self.desktop.getDefaultDesktop()

        if gnomeSelected or kdeSelected:
            hsep = gtk.HSeparator ()
            self.box.pack_start (hsep)

            if gnomeSelected and kdeSelected:
                frame3 = gtk.Frame (_("Please choose your default desktop environment:"))
            else:
                frame3 = gtk.Frame (_("Your desktop environment is:"))
                
            frame3.set_shadow_type (SHADOW_NONE)
            hbox3.pack_start (frame3, gtk.TRUE, gtk.FALSE, 2)

            self.hbox4 = gtk.HBox ()
            frame3.add (self.hbox4)

            # need to have this around so self.display_desktop_pixmap()
            # will work later. (messy)
            self.vbox4 = gtk.VBox()

            if gnomeSelected and kdeSelected:
                vbox3 = gtk.VBox()
                
                gnome_radio = gtk.RadioButton (None, (_("GNOME")))
                vbox3.pack_start (gnome_radio, gtk.TRUE, gtk.FALSE, 2)
                kde_radio = gtk.RadioButton(gnome_radio, (_("KDE")))            
                vbox3.pack_start (kde_radio, gtk.TRUE, gtk.FALSE, 2)

                self.hbox4.pack_start (vbox3)

                self.hbox4.pack_start (self.vbox4)
                
                #--Set the desktop GUI widget to what the user has selected
                if self.origDesktop == "GNOME":
                    gnome_radio.set_active (gtk.TRUE)
                    self.display_desktop_pixmap("GNOME")
                elif self.origDesktop == "KDE":
                    kde_radio.set_active (gtk.TRUE)
                    self.display_desktop_pixmap("KDE")

                gnome_radio.connect ("clicked", self.desktop_cb, "GNOME")
                kde_radio.connect ("clicked", self.desktop_cb, "KDE")
            else:
                self.hbox4.pack_start(gtk.Label(self.origDesktop))
                self.display_desktop_pixmap(self.origDesktop)

            self.box.pack_start (hbox3, gtk.FALSE, gtk.TRUE, 2)
        else:
            gnome_radio = None
            kde_radio = None

        hsep = gtk.HSeparator ()
        self.box.pack_start (hsep)

        frame4 = gtk.Frame (_("Please choose your login type:"))
        frame4.set_shadow_type (SHADOW_NONE)
        hbox4.pack_start (frame4, gtk.TRUE, gtk.FALSE, 2)
        
        self.hbox5 = gtk.HBox (gtk.TRUE, 2)
        frame4.add (self.hbox5)

        self.text = gtk.RadioButton (None, (_("Text")))
        self.graphical = gtk.RadioButton (self.text, (_("Graphical")))

        self.runLevel = self.desktop.getDefaultRunLevel()

        if self.runLevel == 3:
            self.text.set_active (gtk.TRUE)
        elif self.runLevel == 5:
            self.graphical.set_active (gtk.TRUE)

        self.hbox5.pack_start (self.graphical, gtk.FALSE, 2)
        self.hbox5.pack_start (self.text, gtk.FALSE, 2)
        
        self.box.pack_start (hbox4, gtk.FALSE, gtk.TRUE, 2)

        return self.box

class MonitorWindow (InstallWindow):
    windowTitle = N_("Monitor Configuration")
    htmlTag = ("monitor")

    def __init__ (self, ics):
        InstallWindow.__init__ (self, ics)
        self.ics.setNextEnabled (gtk.FALSE)

        # XXX - do not want to go backwards into "Make Bootdisk" screen ever
        self.ics.setPrevEnabled (gtk.FALSE)
        
    def selectCb (self, ctree, node, column):

        if self.ignoreTreeChanges:
            return

        data = self.ctree.node_get_row_data (node)

        if not data:
            # they clicked on a tree tab (a manufacturer node)
            self.ics.setNextEnabled (gtk.FALSE)
            self.setSyncField(self.hEntry, "")
            self.setSyncField(self.vEntry, "")
            self.hEntry.set_editable (gtk.FALSE)
            self.vEntry.set_editable (gtk.FALSE)
            return
        else:
            (parent, monitor) = data
            self.hEntry.set_editable (gtk.TRUE)
            self.vEntry.set_editable (gtk.TRUE)

        if self.currentNode:
            (current_parent, current_monitor) = self.ctree.node_get_row_data (self.currentNode)

        self.currentNode = node

        # otherwise fill in sync fields
        self.setSyncField(self.vEntry, monitor[2])
        self.setSyncField(self.hEntry, monitor[3])
        self.hEntry.set_editable (gtk.TRUE)
        self.vEntry.set_editable (gtk.TRUE)

        self.enableIfSyncsValid(self.hEntry, self.vEntry)


    def getNext (self):
        if self.currentNode:
            (current_parent, current_monitor) = self.ctree.node_get_row_data (self.currentNode)
            self.monitor.setSpecs(self.hEntry.get_text (),
                                  self.vEntry.get_text (),
                                  id=current_monitor[0],
                                  name=current_monitor[0])
        return None

    def moveto (self, ctree, area, node):
        self.ignoreTreeChanges = 1
        self.ctree.node_moveto (node, 0, 0.5, 0.0)
        self.selectCb (self.ctree, node, -1)
        self.ignoreTreeChanges = 0

    def setSyncField(self, field, value):
        self.ignoreEntryChanges = 1
        if value:
            field.set_text(value)
        else:
            field.set_text("")
        self.ignoreEntryChanges = 0

    def enableIfSyncsValid(self, entry, other):
        aval = entry.get_text()
        bval = other.get_text()
        if isValidSyncRange(aval) and isValidSyncRange(bval):
            self.ics.setNextEnabled (gtk.TRUE)
        else:
            self.ics.setNextEnabled (gtk.FALSE)

    def resetCb (self, data):
        (parent, monitor) = self.ctree.node_get_row_data (self.originalNode)

        (old_parent, temp) = self.ctree.node_get_row_data (self.currentNode)

        self.setSyncField(self.hEntry, self.monitor.getMonitorHorizSync(useProbed=1))
        self.setSyncField(self.vEntry, self.monitor.getMonitorVertSync(useProbed=1))
        self.enableIfSyncsValid(self.hEntry, self.vEntry)

        # restore horiz and vert sync ranges in row data as well
        new_monitor = (monitor[0], monitor[1],
                       self.monitor.getMonitorHorizSync(useProbed=1),
                       self.monitor.getMonitorHorizSync(useProbed=1))
        self.ctree.node_set_row_data (self.originalNode, (parent, new_monitor))

        self.ctree.freeze ()

        #--If new selection and old selection have the same parent,
        #  don't collapse or expand anything
        if parent != old_parent:
            self.ctree.expand (parent)
            self.ctree.collapse (old_parent)

        self.ctree.select(self.originalNode)
        self.ctree.thaw ()
        self.ctree.node_moveto (self.originalNode, 0, 0.5, 0.0)

    def insertCb (self, pos, text, len, data, entrys):
        if self.ignoreEntryChanges:
            return

        (entry, other) = entrys
        list = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "-", " ", ".", ","]
        if not(text[:1] in list):
            entry.emit_stop_by_name ("insert-text")

        self.enableIfSyncsValid(entry, other)

    def changedCb (self, data, entrys):
        if self.ignoreEntryChanges:
            return

        (entry, other) = entrys
        self.enableIfSyncsValid(entry, other)

    def getScreen (self, xconfig, monitor):

        self.monitor = monitor
        self.xconfig = xconfig

        # some flags to let us know when to ignore callbacks we caused
        self.ignoreEntryChanges = 0
        self.ignoreTreeChanges = 0

        box = gtk.VBox (gtk.FALSE, 5)

        # Monitor selection tree
        self.ctree = gtk.CTree ()
        self.ctree.set_selection_mode (gtk.SELECTION_BROWSE)

        self.hEntry = gtk.Entry ()
        self.vEntry = gtk.Entry () 

        fn = self.ics.findPixmap("monitor-small.png")
        p = gtk.gdk.pixbuf_new_from_file (fn)
        if p:
            self.monitor_p, self.monitor_b = p.render_pixmap_and_mask()

        # load monitor list and insert into tree
        self.orig_name = self.monitor.getMonitorID(useProbed=1)
        monitorslist = self.monitor.monitorsDB ()
        keys = monitorslist.keys ()
        keys.sort ()

        # treat Generic monitors special
        keys.remove("Generic")
        keys.insert(0, "Generic")

        select = None
        first = 1
        first_node = None
        for man in keys:
            if man == "Generic":
                title = _("Generic")
            else:
                title = man
            parent = self.ctree.insert_node (None, None, (title,), 2,
                                             self.monitor_p, self.monitor_b,
                                             self.monitor_p, self.monitor_b,
                                             is_leaf = gtk.FALSE)
            # save location of top of tree
            if first:
                first_node = parent
                first = 0
                
            models = monitorslist[man]
            models.sort()
            previous_monitor = ""
            for amonitor in models:
                if previous_monitor != "":
                    if amonitor[0] == previous_monitor:
                        continue

                previous_monitor = amonitor[0]
                
                node = self.ctree.insert_node (parent, None, (amonitor[0],), 2)
                self.ctree.node_set_row_data (node, (parent, amonitor))

                if amonitor[0] == self.orig_name:
                    self.originalNode = node
                            
                if amonitor[0] == self.monitor.getMonitorID():
                    select = node
                    selParent = parent

        # Insert DDC probed monitor if it had no match in database
        # or otherwise if we did not detect a monitor at all
        #--Add a category for a DDC probed monitor if a DDC monitor was probed
        if self.orig_name and not self.monitor.lookupMonitor(self.orig_name):
            if self.orig_name != "Unprobed Monitor":
                title = _("DDC Probed Monitor")
            else:
                title = _("Unprobed Monitor")
                
            parent = self.ctree.insert_node (None, first_node,
                                             (title,),
                                             2, self.monitor_p, self.monitor_b,
                                             self.monitor_p, self.monitor_b,
                                             is_leaf = gtk.FALSE)

            self.originalNode = self.ctree.insert_node (parent,
                                  None, (self.orig_name,), 2)
            
            monitordata = (self.orig_name, self.orig_name,
                           self.monitor.getMonitorVertSync(),
                           self.monitor.getMonitorHorizSync())

            self.ctree.node_set_row_data (self.originalNode,
                                          (parent, monitordata))

            # make this the selection
            select = self.originalNode
            selParent = parent

        self.currentNode = select

        self.setSyncField(self.hEntry, self.monitor.getMonitorHorizSync())
        self.setSyncField(self.vEntry, self.monitor.getMonitorVertSync())
        self.enableIfSyncsValid(self.hEntry, self.vEntry)

        self.ctree.connect ("tree_select_row", self.selectCb)
        if select:
            self.ignoreTreeChanges = 1
            self.ctree.select (select)
            self.ctree.expand (selParent)
            self.ctree.connect ("map-event", self.moveto, select)
            self.ignoreTreeChanges = 0

        sw = gtk.ScrolledWindow ()
        sw.add (self.ctree)
        sw.set_policy (gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        box.pack_start (sw, gtk.TRUE, gtk.TRUE)

        self.hEntry.connect ("insert_text", self.insertCb, (self.hEntry, self.vEntry))
        self.vEntry.connect ("insert_text", self.insertCb, (self.vEntry, self.hEntry))

        self.hEntry.connect ("changed", self.changedCb, (self.hEntry, self.vEntry))
        self.vEntry.connect ("changed", self.changedCb, (self.vEntry, self.hEntry))

        self.reset = gtk.Button (_("Restore original values"))
        self.reset.connect ("clicked", self.resetCb)
        align = gtk.Alignment

        align = gtk.Alignment (1, 0.5)
        align.add (self.reset)
        
        synctable = gtk.Table(2, 4, gtk.FALSE)
        hlabel = gtk.Label (_("Horizontal Sync:"))
        hlabel.set_alignment (0, 0.5)
        vlabel = gtk.Label (_("Vertical Sync:"))
        vlabel.set_alignment (0, 0.5)
        
        self.hEntry.set_usize (80, 0)
        self.vEntry.set_usize (80, 0)
        
        hz = gtk.Label (_("kHz"))
        hz.set_alignment (0, 0.5)

        khz = gtk.Label (_("Hz"))
        khz.set_alignment (0, 0.5)
        
        synctable.attach(hlabel, 0, 1, 0, 1, gtk.SHRINK, gtk.FILL, 5)
        synctable.attach(self.hEntry, 1, 2, 0, 1, gtk.SHRINK)
        synctable.attach(hz, 2, 3, 0, 1, gtk.FILL, gtk.FILL, 5)        
        synctable.attach(vlabel, 0, 1, 1, 2, gtk.SHRINK, gtk.FILL, 5)
        synctable.attach(self.vEntry, 1, 2, 1, 2, gtk.SHRINK)
        synctable.attach(khz, 2, 3, 1, 2, gtk.FILL, gtk.FILL, 5)
        synctable.attach(align, 3, 4, 1, 2)
        
        box.pack_start (synctable, gtk.FALSE, gtk.FALSE)
        
        return box

class XConfigWindow (InstallWindow):

    htmlTag ="xconf"
    windowTitle = N_("Graphical Interface (X) Configuration")
        
    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)
        self.ics = ics

    def getNext (self):
        if self.skip.get_active():
            self.dispatch.skipStep("monitor")
            self.dispatch.skipStep("xcustom")
            self.dispatch.skipStep("writexconfig")
            self.xconfig.skipx = 1

            return None
        else:
            self.dispatch.skipStep("monitor", skip = 0)
            self.dispatch.skipStep("xcustom", skip = 0)
            self.dispatch.skipStep("writexconfig", skip = 0)
            self.xconfig.skipx = 0

        # set videocard type (assuming we're working with PRIMARY card)
        if self.selected_card:
            primary_card = self.videocard.primaryCard()
            primary_card.setCardData(self.selected_card)
            primary_card.setDevID (self.selected_card["NAME"])
            primary_card.setDescription (self.selected_card["NAME"])

            # pull out resolved version of card data
            card_data = primary_card.getCardData()
            if (card_data.has_key("DRIVER") and
                not card_data.has_key("UNSUPPORTED")):
                server = "XFree86"
            else:
                server = "XF86_" + card_data["SERVER"]

            primary_card.setXServer(server)
        else:
            self.intf.messageWindow(_("Unspecified video card"),
                            _("You need to pick a video card before "
                              "X configuration can continue.  If you "
                              "want to skip X configuration entirely "
                              "choose the 'Skip X Configuration' button."))
            raise gui.StayOnScreen

        
        # see if they actually picked a card, otherwise keep going



        # sniff out the selected ram size
        menu = self.ramOption.get_menu ().get_active()
        index = 0
        for menu_item in self.ramOption.get_menu ().children ():
            if menu_item == menu:
                break
            index = index + 1

        vidram = self.videocard.possible_ram_sizes()[index]

        self.videocard.primaryCard().setVideoRam(str(vidram))
        self.xconfig.setVideoCard(self.videocard.primaryCard())
        self.xconfig.filterModesByMemory ()
        
        return None

    def skipToggled (self, widget, *args):
        self.configbox.set_sensitive (not widget.get_active ())

    def movetree (self, ctree, area, selected_node):
        if self.selected_node == None:
            print "bad selected_node = None!!"
            return
        
        self.ctree.freeze()
        node = self.selected_node
        (parent_node, cardname) = self.ctree.node_get_row_data(node)

        self.ctree.select(node)
        self.ctree.expand(parent_node)
        self.ctree.thaw()
        self.ctree.node_moveto(node, 0, 0.5, 0)

    def movetree2 (self, ctree, area, node):
        self.ctree.freeze()
        node = self.orig_node
        (current_parent_node, cardname2) = self.ctree.node_get_row_data(node)
        self.selected_node = node
        self.ctree.select(node)
        (parent_node, cardname) = self.ctree.node_get_row_data(node)                        
        self.ctree.expand(parent_node)
        self.ctree.thaw()
        self.ctree.node_moveto(node, 0, 0.5, 0)

    def selectCb_tree (self, ctree, node, column):
        try:
            self.current_node = node
            (parent, cardname) = ctree.node_get_row_data (node)
            if cardname:
                card = self.cards[cardname]
                depth = 0

                self.selected_card = card
        except:
            print "selectCb_tree failed"
            pass
            
    def restorePressed (self, ramMenu):
        try:
            (current_parent_node, cardname1) = self.ctree.node_get_row_data(self.current_node)
            (original_parent_node, cardname2) = self.ctree.node_get_row_data(self.orig_node)

            if current_parent_node != original_parent_node:
                self.ctree.collapse(current_parent_node)

            if cardname1 != cardname2:
                self.movetree2(self.ctree, self.orig_node, 0)
            else:
                pass
        except:
            pass
        
        self.ramOption.remove_menu ()
        self.selectVideoRamMenu(1)
        self.ramOption.set_menu (self.ramMenu)
        
    def desktopCb (self, widget, desktop):
        self.newDesktop = desktop

    def selectVideoRamMenu(self, useProbed):

        #--Some video cards don't return exact numbers, so do some hacks
        try:
            vidRam = string.atoi (self.videocard.primaryCard(useProbed=useProbed).getVideoRam())
        except:
            vidRam = 1024

        count = self.videocard.index_closest_ram_size(vidRam)
        self.ramMenu.set_active(count)

    # XConfigWindow tag="xconf"
    def getScreen (self, dispatch, xconfig, videocard, intf):
        self.ics.setHelpEnabled (gtk.TRUE)

        def makeFormattedLabel(text):
            label = gtk.Label (text)
            label.set_justify (gtk.JUSTIFY_LEFT)
            label.set_line_wrap (gtk.TRUE)        
            label.set_alignment (0.0, 0.5)
            label.set_usize (400, -1)
            return label
            
        self.dispatch = dispatch
        self.videocard = videocard
        self.xconfig = xconfig
        self.intf = intf

        box = gtk.VBox (gtk.FALSE, 0)
        box.set_border_width (0)

        self.autoBox = gtk.VBox (gtk.FALSE, 5)

        arch = iutil.getArch()
        if arch == "alpha" or arch == "ia64":
            label = makeFormattedLabel (_("Your video ram size can not be "
                                          "autodetected.  Choose your video "
                                          "ram size from the choices below:"))
            box.pack_start (label, gtk.FALSE)
        elif arch == "i386":
            # but we can on everything else
            self.autoBox = gtk.VBox (gtk.FALSE, 5)

            label = makeFormattedLabel (_("In most cases your video hardware "
                                          "can be probed to automatically "
                                          "determine the best settings for "
                                          "your display."))
            self.autoBox.pack_start (label, gtk.FALSE)

            label = makeFormattedLabel (_("If the probed settings do not "
                                          "match your hardware, select the "
                                          "correct hardware settings below:"))
            self.autoBox.pack_start (label, gtk.FALSE)

            box.pack_start (self.autoBox, gtk.FALSE)
        else:
            # sparc
            return
            
        # Monitor selection tree
        self.ctree = gtk.CTree ()
        self.ctree.set_selection_mode (gtk.SELECTION_BROWSE)

        fn = self.ics.findPixmap("videocard.png")
        p = gtk.gdk.pixbuf_new_from_file (fn)
        if p:
            self.videocard_p, self.videocard_b = p.render_pixmap_and_mask()

        self.manufacturer_nodes = {}

        # put Generic and other first
        self.manufacturer_nodes["Generic"] = self.ctree.insert_node(None, None,
                                                                   (_("Generic"),), 2,
                                           self.videocard_p, self.videocard_b,
                                           self.videocard_p, self.videocard_b,
                                           gtk.FALSE)
        self.manufacturer_nodes["Other"] = self.ctree.insert_node(None, None,
                                                                   (_("Other"),), 2,
                                           self.videocard_p, self.videocard_b,
                                           self.videocard_p, self.videocard_b,
                                           gtk.FALSE)
        
        for man in self.videocard.manufacturerDB():
            self.manufacturer_nodes[man] = self.ctree.insert_node (None, None,
                                                                   (man,), 2,
                                           self.videocard_p, self.videocard_b,
                                           self.videocard_p, self.videocard_b,
                                           gtk.FALSE)

        self.cards = self.videocard.cardsDB()
        cards = self.cards.keys()
        cards.sort()

        other_cards = copy.copy(cards)
        current_cardsel = None
        probed_card = None
        self.current_node = None
        self.orig_node = None
        self.selected_node = None
        if self.videocard.primaryCard():
            carddata = self.videocard.primaryCard().getCardData(dontResolve=1)
            if carddata:
                current_cardsel = carddata["NAME"]
            else:
                current_cardsel = None

            carddata = self.videocard.primaryCard(useProbed=1).getCardData()
            if carddata:
                probed_card = carddata["NAME"]
            else:
                probed_card = None
            
        for card in cards:
            temp = string.lower(card)

            # don't let them configure VGA16
            if card in Videocard_blacklist:
                other_cards.remove(card)
                continue

            manufacturers = self.videocard.manufacturerDB()
            manufacturers.append("Generic")
            for man in manufacturers:
                if string.lower(man) == temp[:len(man)]:
                    node = self.ctree.insert_node (self.manufacturer_nodes[man], None, (card,), 2)
                    self.ctree.node_set_row_data(node, (self.manufacturer_nodes[man], card))
                    other_cards.remove(card)

            # note location of current selection and probed card
            if card == current_cardsel:
                self.current_node = node
                self.selected_node = node
            
            if card == probed_card:
                self.orig_node = node

        # now add cards not categorized into above manufacturers
        for card in other_cards:
            node = self.ctree.insert_node (self.manufacturer_nodes["Other"], None, (card,), 2)
            self.ctree.node_set_row_data(node, (self.manufacturer_nodes["Other"], card))
            
            # note location of current selection and probed card
            if card == current_cardsel:
                self.current_node = node
                self.selected_node = node
            
            if card == probed_card:
                self.orig_node = node

        # set to None initially, changed by selectCb_tree callback
        self.selected_card = None

        #- Once ctree is realized then expand  branch and select selected item.
        self.ctree.connect ("tree_select_row", self.selectCb_tree)
        self.ctree.connect ("map-event", self.movetree, self.selected_node)

        sw = gtk.ScrolledWindow ()
        sw.set_policy (gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        sw.add (self.ctree)
        box.pack_start (sw, gtk.TRUE)

        #Memory configuration menu
        hbox = gtk.HBox()
        hbox.set_border_width(3)
            
        label = gtk.Label (_("Video card RAM: "))

        self.ramOption = gtk.OptionMenu()
        self.ramOption.set_usize (40, 20)
        self.ramMenu = gtk.Menu()

        for mem in self.videocard.possible_ram_sizes():
            if mem < 1000:
                tag = "%d KB" % (mem)
            else:
                tag = "%d MB" % (mem/1024)

            memitem = gtk.MenuItem(tag)
            self.ramMenu.add(memitem)

        self.selectVideoRamMenu(0)
        hbox.pack_start(label, gtk.FALSE)
        hbox.pack_start(self.ramOption, gtk.TRUE, gtk.TRUE, 25)

        self.ramOption.set_menu (self.ramMenu)
        box.pack_start (hbox, gtk.FALSE)

        restore = gtk.Button (_("Restore original values"))
        restore.connect ("clicked", self.restorePressed)
        hbox.pack_start(restore, gtk.FALSE, 25)
        
        self.skip = gtk.CheckButton (_("Skip X Configuration"))
        self.skip.connect ("toggled", self.skipToggled) 
        
        hbox = gtk.HBox (gtk.TRUE, 5)
        
        self.topbox = gtk.VBox (gtk.FALSE, 5)
        self.topbox.set_border_width (5)
        self.topbox.pack_start (box, gtk.TRUE, gtk.TRUE)
        self.topbox.pack_start (self.skip, gtk.FALSE)
        
        self.configbox = box
        
        self.skip.set_active (self.dispatch.stepInSkipList("monitor"))
        
        return self.topbox
