#
# xconfig_gui: gui X configuration
#
# Brent Fox <bfox@redhat.com>
#
# Copyright 2000-2002 Red Hat, Inc.
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
import gobject
import gtk
from iw_gui import *

from rhpl.log import log
from rhpl.translate import _, N_
from rhpl.monitor import isValidSyncRange

from desktop import ENABLE_DESKTOP_CHOICE

from gui import setupTreeViewFixupIdleHandler

ddc_monitor_string = _("DDC Probed Monitor")
unprobed_monitor_string = _("Unprobed Monitor")


### why is this here???
def makeFormattedLabel(text):
    label = gtk.Label (text)
    label.set_justify (gtk.JUSTIFY_LEFT)
    label.set_line_wrap (gtk.TRUE)        
    label.set_alignment (0.0, 0.5)
    label.set_size_request (400, -1)
    return label


class XCustomWindow (InstallWindow):

    htmlTag = "xcustom"
    windowTitle = N_("Customize Graphical Configuration")

    def __init__ (self, ics):
        InstallWindow.__init__ (self, ics)
        self.ics.setNextEnabled (gtk.TRUE)


    def getPrev(self):
	# restore settings
	self.xsetup.xhwstate.set_resolution(self.origres)
	self.xsetup.xhwstate.set_colordepth(self.origdepth)
	return None
	
    def getNext (self):
	
        self.xsetup.xhwstate.set_colordepth(self.selectedDepth)
	self.xsetup.xhwstate.set_resolution(self.selectedRes)

	if ENABLE_DESKTOP_CHOICE:
	    self.desktop.setDefaultDesktop (self.newDesktop)

	if self.instClass.showLoginChoice:
	    if self.text.get_active ():
		rl = 3
	    elif self.graphical.get_active ():
		rl = 5
	else:
	    # default to 5 if we didnt give them a choice
	    rl = 5

        self.desktop.setDefaultRunLevel(rl)


    def testPressed (self, widget, *args):
	log("Somehow X test was attempted")
	return
    
    def numCompare (self, first, second):
        if first > second:
            return 1
        elif first < second:
            return -1
        return 0

    def depth_cb (self, widget):
	self.ignore_res_cb = 1
        loc = self.depth_optionmenu.get_history()

        if self.selectedDepth == self.avail_depth[loc]:
	    self.ignore_res_cb = 0
            return

        self.selectedDepth = self.avail_depth[loc]
	self.xsetup.xhwstate.set_colordepth(self.selectedDepth)

	# now we set color depth, read out what modes are now supported
	self.selectedRes = self.xsetup.xhwstate.get_resolution()
	self.avail_res = self.xsetup.xhwstate.available_resolutions()

	self.create_res_optionmenu()

        if self.selectedRes not in self.avail_res:
	    self.selectedRes = self.avail_res[-1]
	    
	self.currentRes = self.avail_res.index(self.selectedRes)
	self.res_optionmenu.set_history(self.currentRes)
	self.ignore_res_cb = 0

    def res_cb (self, widget):
	if self.ignore_res_cb:
	    return
	
        newres = self.res_optionmenu.get_history()
        if self.currentRes == newres:
            return
        
        self.currentRes = newres
        self.selectedRes = self.avail_res[self.currentRes]
	self.xsetup.xhwstate.set_resolution(self.selectedRes)

        self.swap_monitor (self.currentRes)

    def create_res_optionmenu(self):
	if self.res_optionmenu is None:
	    self.res_optionmenu = gtk.OptionMenu()

	if self.res_menu is not None:
	    self.res_optionmenu.remove_menu()

	self.res_menu = gtk.Menu()
	
	for r in self.avail_res:
	    item = gtk.MenuItem(r)
	    item.show()
	    self.res_menu.add(item)

	self.res_optionmenu.set_menu(self.res_menu)

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

	try:
	    self.load_monitor_preview_pixmap(self.monitor_pixmaps[num])
	except:
	    log("Unable to load monitor preview #%s", num)

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
    def getScreen (self, xsetup, monitor, videocard, desktop, comps,
                   instClass, instPath):

        self.xsetup = xsetup
        self.monitor = monitor
        self.videocard = videocard
        self.desktop = desktop
	self.instClass = instClass

	if not xsetup.imposed_sane_default:
	    xsetup.xhwstate.choose_sane_default()
	    xsetup.imposed_sane_default = 1

	# save so we can restore if necessary going back
	self.origres = self.xsetup.xhwstate.get_resolution()
	self.origdepth = self.xsetup.xhwstate.get_colordepth()

        self.instPath = instPath

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

        hbox1 = gtk.HBox (gtk.FALSE, 5)
        hbox3 = gtk.HBox (gtk.FALSE, 5)
        hbox4 = gtk.HBox (gtk.FALSE, 5)

        frame1 = gtk.Frame (_("_Color Depth:"))
        frame1.get_label_widget().set_property("use-underline", gtk.TRUE)
        frame1.set_shadow_type (gtk.SHADOW_NONE)
        frame1.set_border_width (10)
        hbox1.pack_start(frame1, gtk.TRUE, gtk.FALSE, 0)

        # determine video modes available for this card/monitor combo
	self.avail_depth = self.xsetup.xhwstate.available_color_depths()

        self.depth_list = [(_("256 Colors (8 Bit)")),
		      (_("High Color (16 Bit)")),
		      (_("True Color (24 Bit)"))]
        self.bit_depth = [8, 16, 24]

	# create option menu for bit depth
	self.depth_optionmenu = gtk.OptionMenu()
	self.depth_menu = gtk.Menu()

	for i in range(0, len(self.depth_list)):
	    if self.bit_depth[i] in self.avail_depth:
		d = self.depth_list[i]
		item = gtk.MenuItem(d)
		item.show()
		self.depth_menu.add(item)

	self.depth_optionmenu.set_menu(self.depth_menu)
	
        frame1.add (self.depth_optionmenu)
        frame1.get_label_widget().set_mnemonic_widget(self.depth_optionmenu)

	# now we do screen resolution
        frame2 = gtk.Frame (_("_Screen Resolution:"))
        frame2.get_label_widget().set_property("use-underline", gtk.TRUE)
        frame2.set_shadow_type (gtk.SHADOW_NONE)
        frame2.set_border_width (10)
        hbox1.pack_start (frame2, gtk.TRUE, gtk.FALSE, 2)

        self.avail_res = self.xsetup.xhwstate.available_resolutions()
	
	self.res_optionmenu = None
	self.res_menu = None
	self.create_res_optionmenu()

        frame2.add (self.res_optionmenu)
        frame2.get_label_widget().set_mnemonic_widget(self.res_optionmenu)

        # apply current configuration to UI
        self.selectedDepth = self.xsetup.xhwstate.get_colordepth()
        self.selectedRes   = self.xsetup.xhwstate.get_resolution()

	if self.selectedDepth not in self.avail_depth:
	    self.selectedDepth = self.avail_depth[-1]

	idx = self.avail_depth.index(self.selectedDepth)
	self.depth_optionmenu.set_history(idx)

	if self.selectedRes not in self.avail_res:
	    self.selectedRes = self.avail_res[-1]
	    
	self.currentRes = self.avail_res.index(self.selectedRes)
	self.res_optionmenu.set_history (self.currentRes)
        self.swap_monitor(self.currentRes)

	self.depth_optionmenu.connect ("changed", self.depth_cb)
	self.ignore_res_cb = 0
        self.res_optionmenu.connect ("changed", self.res_cb)

        self.box.pack_start (hbox1, gtk.FALSE)

        #--If both KDE and GNOME are selected
        if comps:
            gnomeSelected = (comps.packages.has_key('gnome-session')
                             and comps.packages['gnome-session'].selected)
            kdeSelected = (comps.packages.has_key('kdebase')
                           and comps.packages['kdebase'].selected)
        else:
            gnomeSelected = 0
            kdeSelected = 0

        self.newDesktop = ""
        self.origDesktop = self.desktop.getDefaultDesktop()

	if (ENABLE_DESKTOP_CHOICE) and (gnomeSelected or kdeSelected):
            hsep = gtk.HSeparator ()
            self.box.pack_start (hsep)

            if gnomeSelected and kdeSelected:
                frame3 = gtk.Frame (_("Please choose your default desktop environment:"))
            else:
                frame3 = gtk.Frame (_("Your desktop environment is:"))
                
            frame3.set_shadow_type (gtk.SHADOW_NONE)
            hbox3.pack_start (frame3, gtk.TRUE, gtk.FALSE, 2)

            self.hbox4 = gtk.HBox ()
            frame3.add (self.hbox4)

            # need to have this around so self.display_desktop_pixmap()
            # will work later. (messy)
            self.vbox4 = gtk.VBox()

            if gnomeSelected and kdeSelected:
                vbox3 = gtk.VBox()
                
                gnome_radio = gtk.RadioButton (None, (_("GNO_ME")))
                vbox3.pack_start (gnome_radio, gtk.TRUE, gtk.FALSE, 2)
                kde_radio = gtk.RadioButton(gnome_radio, (_("_KDE")))            
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

	# see if we should allow them to choose graphical or text login
	if self.instClass.showLoginChoice:
	    frame4 = gtk.Frame (_("Please choose your login type:"))
	    frame4.set_shadow_type (gtk.SHADOW_NONE)
	    hbox4.pack_start (frame4, gtk.TRUE, gtk.FALSE, 2)

	    self.hbox5 = gtk.HBox (gtk.TRUE, 2)
	    frame4.add (self.hbox5)

	    self.text = gtk.RadioButton (None, (_("_Text")))
	    self.graphical = gtk.RadioButton (self.text, (_("_Graphical")))

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
        self.ics.setPrevEnabled (gtk.TRUE)
        
    def getNext (self):
        if self.currentMonitor:
            monHoriz = string.replace(self.hEntry.get_text(), " ", "")
            monVert = string.replace(self.vEntry.get_text(), " ", "")

	    if self.currentMonitor[:len(ddc_monitor_string)] == ddc_monitor_string:
		idname = "DDCPROBED"
	    elif self.currentMonitor == unprobed_monitor_string:
		idname = "Unprobed Monitor"
	    else:
		idname = self.currentMonitor

	    # XXX - this is messed up - we set the monitor object in instdata
	    #       to the current values, then we have to push it into the
	    #       xhwstate as well.  Need to join this operation somehow.
            self.monitor.setSpecs(monHoriz,
                                  monVert,
                                  id=idname,
                                  name=self.currentMonitor)

	    # shove into hw state object, force it to recompute available modes
	    self.xsetup.xhwstate.monitor = self.monitor
	    self.xsetup.xhwstate.set_monitor_name(self.currentMonitor)
	    self.xsetup.xhwstate.set_hsync(monHoriz)
	    self.xsetup.xhwstate.set_vsync(monVert)
	    self.xsetup.xhwstate.recalc_mode()
	    
        return None

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

    def setCurrent(self, monitorname, recenter=1):
	self.ignoreEvents = 1
	self.currentMonitor = monitorname

        parent = None
        iter = self.monitorstore.get_iter_first()

        # iterate over the list, looking for the current monitor selection
        while iter:
            # if this is a parent node, get the first child and iter over them
            if self.monitorstore.iter_has_child(iter):
                parent = iter
                iter = self.monitorstore.iter_children(parent)
                continue
            # if it's not a parent node and the mouse matches, select it.
            elif self.monitorstore.get_value(iter, 0) == monitorname:
                path = self.monitorstore.get_path(parent)
                self.monitorview.expand_row(path, gtk.TRUE)
                selection = self.monitorview.get_selection()
                selection.unselect_all()
                selection.select_iter(iter)
                path = self.monitorstore.get_path(iter)
                col = self.monitorview.get_column(0)
                self.monitorview.set_cursor(path, col, gtk.FALSE)
                if recenter:
                    self.monitorview.scroll_to_cell(path, col, gtk.TRUE,
                                                  0.0, 0.5)
                break
            # get the next row.
            iter = self.monitorstore.iter_next(iter)
	    
            # if there isn't a next row and we had a parent, go to the node
            # after the parent we've just gotten the children of.
            if not iter and parent:
                parent = self.monitorstore.iter_next(parent)
                iter = parent

	# set sync rates
	if monitorname == self.origMonitorName:
	    hsync = self.origHsync
	    vsync = self.origVsync
	elif monitorname[:len(ddc_monitor_string)] == ddc_monitor_string:
	    hsync = self.ddcmon[2]
	    vsync = self.ddcmon[3]
	elif monitorname == unprobed_monitor_string:
	    hsync = "31.5"
	    vsync = "50-61"
#	    hsync = self.ddcmon[2]
#	    vsync = self.ddcmon[3]
	else:
	    monname = self.monitorstore.get_value(iter, 0)
	    rc = self.monitor.lookupMonitorByName(monname)
	    if rc:
		(model, eisa, vsync, hsync) = rc
	    else:
		# no match for model ACK!
		print "Could not find match for monitor %s in list!" % monname
		print "How could this happen?"

		# use 640x480 to be safe
		hsync = "31.5"
		vsync = "50-61"
		
        self.setSyncField(self.hEntry, hsync)
        self.setSyncField(self.vEntry, vsync)
        self.enableIfSyncsValid(self.hEntry, self.vEntry)

	self.ignoreEvents = 0
	
    def selectMonitorType (self, selection, *args):
	if self.ignoreEvents:
	    return

	(monxxx, iter) = selection.get_selected()
	if iter:
	    monid = monxxx.get_value(iter, 0)
		
	    self.setCurrent(monid, recenter=0)
	else:
	    print "unknown error in selectMonitorType!"

    def monitorviewSelectCb(self, path):
	# XXX 01/09/2002 - work around broken gtkwidget, fix when jrb fixes
	if len(path) == 1:
	    if self.lastvalidselection:
		self.ignoreEvents = 1
		selection = self.monitorview.get_selection()
		if not selection.path_is_selected(self.lastvalidselection):
		    selection.select_path(self.lastvalidselection)
		self.ignoreEvents = 0
	    return 0

	self.lastvalidselection = path
	
	return 1

    def resetCb (self, data):
	# if we have a ddc probe value, reset to that
	if self.ddcmon:
	    self.setCurrent(ddc_monitor_string + " - " + self.ddcmon[1])
	else:
	    self.setCurrent(unprobed_monitor_string)

	self.setSyncField(self.hEntry, self.origHsync)
        self.setSyncField(self.vEntry, self.origVsync)

        self.enableIfSyncsValid(self.hEntry, self.vEntry)

	self.currentMonitor = self.origMonitorName

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

    def getScreen (self, xsetup, monitor):

        self.monitor = monitor
        self.xsetup = xsetup

        # some flags to let us know when to ignore callbacks we caused
        self.ignoreEntryChanges = 0
        self.ignoreEvents = 0

	self.lastvalidselection = None

        box = gtk.VBox (gtk.FALSE, 5)

	label = makeFormattedLabel (_("In most cases, the monitor can be "
				      "automatically detected. If the "
				      "detected settings are not correct "
				      "for the monitor, select the right "
				      "settings."))
	box.pack_start (label, gtk.FALSE)

        # Monitor selection tree
	self.monitorstore = gtk.TreeStore(gobject.TYPE_STRING,
					  gobject.TYPE_STRING)
        self.hEntry = gtk.Entry ()
        self.vEntry = gtk.Entry () 

        fn = self.ics.findPixmap("monitor-small.png")
        p = gtk.gdk.pixbuf_new_from_file (fn)
        if p:
            self.monitor_p, self.monitor_b = p.render_pixmap_and_mask()

        # load monitor list and insert into tree
        self.origMonitorID = self.monitor.getMonitorID()
	self.origMonitorName = self.monitor.getMonitorName()
	if not self.origMonitorName:
	    self.origMonitorName = self.origMonitorID

        self.origHsync = self.monitor.getMonitorHorizSync()
        self.origVsync = self.monitor.getMonitorVertSync()

        monitorslist = self.monitor.monitorsDB ()
        keys = monitorslist.keys ()
        keys.sort ()

        # treat Generic monitors special
        keys.remove("Generic")
        keys.insert(0, "Generic")

	self.currentMonitor = None
	toplevels={}

        # Insert DDC probed monitor if it had no match in database
        # or otherwise if we did not detect a monitor at all
        #--Add a category for a DDC probed monitor if a DDC monitor was probed
	self.ddcmon = self.monitor.getDDCProbeResults()
	if self.ddcmon:
	    title = ddc_monitor_string + " - " + self.ddcmon[1]
	else:
	    title = unprobed_monitor_string

	man = title
	toplevels[man] = self.monitorstore.append(None)
	self.monitorstore.set_value(toplevels[man], 0, title)
	iter = self.monitorstore.append(toplevels[man])
	self.monitorstore.set_value(iter, 0, title)

	# set as current monitor if necessary
	if self.origMonitorID == "DDCPROBED" or self.origMonitorID == "Unprobed Monitor":
	    self.currentMonitor = title
	    self.origMonitorName = title

	# now insert rest of monitors, unless we match the ddc probed id
        for man in keys:
            if man == "Generic":
                title = _("Generic")
            else:
                title = man

	    toplevels[man] = self.monitorstore.append(None)
	    self.monitorstore.set_value(toplevels[man], 0, man)
                
            models = monitorslist[man]
            models.sort()
            previous_monitor = ""
            for amonitor in models:
                if previous_monitor != "":
                    if amonitor[0] == previous_monitor:
                        continue

		if self.ddcmon and string.upper(self.ddcmon[0]) == string.upper(amonitor[1]):
		    continue

                previous_monitor = amonitor[0]
		iter = self.monitorstore.append(toplevels[man])
		self.monitorstore.set_value(iter, 0, amonitor[0])

                if amonitor[0] == self.monitor.getMonitorID():
                    self.currentMonitor = amonitor[0]

        self.monitorview = gtk.TreeView(self.monitorstore)
        self.monitorview.set_property("headers-visible", gtk.FALSE)
        col = gtk.TreeViewColumn(None, gtk.CellRendererText(), text=0)
        self.monitorview.append_column(col)

        sw = gtk.ScrolledWindow ()
        sw.add (self.monitorview)
        sw.set_policy (gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
	sw.set_shadow_type(gtk.SHADOW_IN)
        box.pack_start (sw, gtk.TRUE, gtk.TRUE)

	self.setCurrent(self.currentMonitor)
        selection = self.monitorview.get_selection()
        selection.connect("changed", self.selectMonitorType)
	selection.set_select_function(self.monitorviewSelectCb)
	
        self.hEntry.connect ("insert_text", self.insertCb, (self.hEntry, self.vEntry))
        self.vEntry.connect ("insert_text", self.insertCb, (self.vEntry, self.hEntry))

        self.hEntry.connect ("changed", self.changedCb, (self.hEntry, self.vEntry))
        self.vEntry.connect ("changed", self.changedCb, (self.vEntry, self.hEntry))

        self.reset = gtk.Button (_("Restore _original values"))
        self.reset.connect ("clicked", self.resetCb)
        align = gtk.Alignment

        align = gtk.Alignment (1, 0.5)
        align.add (self.reset)
        
        synctable = gtk.Table(2, 4, gtk.FALSE)
        hlabel = gui.MnemonicLabel (_("Hori_zontal Sync:"))
        hlabel.set_alignment (0, 0.5)
        hlabel.set_mnemonic_widget(self.hEntry)
        vlabel = gui.MnemonicLabel (_("_Vertical Sync:"))
        vlabel.set_alignment (0, 0.5)
        vlabel.set_mnemonic_widget(self.vEntry)
        
        self.hEntry.set_size_request (80, -1)
        self.vEntry.set_size_request (80, -1)
        
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
	
	setupTreeViewFixupIdleHandler(self.monitorview, self.monitorstore)

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
            self.xsetup.skipx = 1

            return None
        else:
            self.dispatch.skipStep("monitor", skip = 0)
            self.dispatch.skipStep("xcustom", skip = 0)
            self.dispatch.skipStep("writexconfig", skip = 0)
            self.xsetup.skipx = 0

        # set videocard type (assuming we're working with PRIMARY card)
        if self.currentCard:
	    try:
		selected = self.cards[self.currentCard]
	    except:
		self.intf.messageWindow(_("Unknown video card"),
					_("An error has occurred selecting "
					  "the video card %s. Please report "
					  "this error to bugzilla.redhat.com.")
					%self.currentCard)
		raise gui.StayOnScreen

            primary_card = self.videocard.primaryCard()
            primary_card.setCardData(selected)
            primary_card.setDevID (selected["NAME"])
            primary_card.setDescription (selected["NAME"])

            # pull out resolved version of card data
            card_data = primary_card.getCardData()
            if (card_data.has_key("DRIVER") and
                not card_data.has_key("UNSUPPORTED")):
                server = "XFree86"
            else:
                server = "XF86_" + card_data["SERVER"]

            primary_card.setXServer(server)
        else:
	    selected = None

	if selected == None:
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
        for menu_item in self.ramOption.get_menu ().get_children ():
            if menu_item == menu:
                break
            index = index + 1

        vidram = self.videocard.possible_ram_sizes()[index]

	# lots of duplication here complicated by factor we have a
	# videocard object as part of instdata and in xhwstate!!
	# need to consolidate
        self.videocard.primaryCard().setVideoRam(str(vidram))
	self.xsetup.xhwstate.set_videocard_ram(vidram)
        self.xsetup.xhwstate.set_videocard_card(self.videocard.primaryCard())
        return None

    def skipToggled (self, widget, *args):
        self.configbox.set_sensitive (not widget.get_active ())

    def selectCardType (self, selection, *args):
	if self.ignoreEvents:
	    return

	(model, iter) = selection.get_selected()
	if iter:
	    self.currentCard = model.get_value(iter, 0)
	else:
	    print "unknown error in selectCardType!"
            
    def restorePressed (self, button):
	self.currentCard = self.probedCard
	self.currentMem = self.probedMem
        self.setCurrent(self.probedCard, self.probedMem)
        
    def desktopCb (self, widget, desktop):
        self.newDesktop = desktop

    def cardviewSelectCb(self, path):
	# XXX 01/09/2002 - work around broken gtkwidget, fix when jrb fixes
	if len(path) == 1:
	    if self.lastvalidselection:
		self.ignoreEvents = 1
		selection = self.cardview.get_selection()
		if not selection.path_is_selected(self.lastvalidselection):
		    selection.select_path(self.lastvalidselection)
		self.ignoreEvents = 0
	    return 0

	self.lastvalidselection = path
	
	return 1

    def setCurrent(self, cardname, currentMem, recenter=1):
        self.ignoreEvents = 1
        self.currentCard = cardname

        parent = None
        iter = self.cardstore.get_iter_first()
        # iterate over the list, looking for the current mouse selection
        while iter:
            # if this is a parent node, get the first child and iter over them
            if self.cardstore.iter_has_child(iter):
                parent = iter
                iter = self.cardstore.iter_children(parent)
                continue
            # if it's not a parent node and the mouse matches, select it.
            elif self.cardstore.get_value(iter, 0) == cardname:
                path = self.cardstore.get_path(parent)
                self.cardview.expand_row(path, gtk.TRUE)
                selection = self.cardview.get_selection()
                selection.unselect_all()
                selection.select_iter(iter)
                path = self.cardstore.get_path(iter)
                col = self.cardview.get_column(0)
                self.cardview.set_cursor(path, col, gtk.FALSE)
                if recenter:
                    self.cardview.scroll_to_cell(path, col, gtk.TRUE,
                                                  0.0, 0.5)
                break
            # get the next row.
            iter = self.cardstore.iter_next(iter)
            # if there isn't a next row and we had a parent, go to the node
            # after the parent we've just gotten the children of.
            if not iter and parent:
                parent = self.cardstore.iter_next(parent)
                iter = parent

        #--Some video cards don't return exact numbers, so do some hacks
        try:
            vidRam = string.atoi (currentMem)
        except:
            vidRam = 1024

        count = self.videocard.index_closest_ram_size(vidRam)
	self.ramOption.remove_menu()
        self.ramMenu.set_active(count)
	self.ramOption.set_menu(self.ramMenu)

	self.ignoreEvents = 0

    # XConfigWindow tag="xconf"
    def getScreen (self, dispatch, xsetup, videocard, intf):
        self.ics.setHelpEnabled (gtk.TRUE)

        self.dispatch = dispatch
        self.videocard = videocard
        self.xsetup = xsetup
        self.intf = intf

	self.lastvalidselection = None

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

            label = makeFormattedLabel (_("In most cases, the video hardware "
                                          "can be automatically detected. "
                                          "If the detected settings are not "
                                          "correct for the hardware, select "
					  "the right settings."))
            self.autoBox.pack_start (label, gtk.FALSE)

            box.pack_start (self.autoBox, gtk.FALSE)
        else:
            # sparc
            return

	# load in card database
        self.cards = self.videocard.cardsDB()
        cards = self.cards.keys()
        cards.sort()

        other_cards = copy.copy(cards)
        self.currentCard = None
        self.probedCard = None
        if self.videocard.primaryCard():
            carddata = self.videocard.primaryCard().getCardData(dontResolve=1)
            if carddata:
                self.currentCard = carddata["NAME"]
            else:
                self.currentCard = None

            carddata = self.videocard.primaryCard(useProbed=1).getCardData()
            if carddata:
                self.probedCard = carddata["NAME"]
            else:
                self.probedCard = None

	# load images of videocard
        fn = self.ics.findPixmap("videocard.png")
        p = gtk.gdk.pixbuf_new_from_file (fn)
        if p:
            self.videocard_p, self.videocard_b = p.render_pixmap_and_mask()

        # Videocard selection tree - preset 'Generic' and 'Other' nodes
	self.cardstore = gtk.TreeStore(gobject.TYPE_STRING,
				       gobject.TYPE_STRING)

	toplevels={}

	# add "Generic" in before "Other" if supporting XFree86 3.x
	# Note other changes in videocard.py and elsewhere required to support
	# XFree86 3.x again
	manufacturers = ["Other"] + self.videocard.manufacturerDB()
	for man in manufacturers:
	    toplevels[man] = self.cardstore.append(None)
	    self.cardstore.set_value(toplevels[man], 0, man)

	# now go through cards and matchup with manufacturers
        for card in cards:
            temp = string.lower(card)

            for man in manufacturers:
                if string.lower(man) == temp[:len(man)]:
		    parent = toplevels.get(man)
		    iter = self.cardstore.append(parent)
		    self.cardstore.set_value(iter, 0, card)
                    other_cards.remove(card)

        # now add cards not categorized into above manufacturers
        for card in other_cards:
	    parent = toplevels.get("Other")
	    iter = self.cardstore.append(parent)
	    self.cardstore.set_value(iter, 0, card)

        self.cardview = gtk.TreeView(self.cardstore)
        self.cardview.set_property("headers-visible", gtk.FALSE)
        col = gtk.TreeViewColumn(None, gtk.CellRendererText(), text=0)
        self.cardview.append_column(col)
        selection = self.cardview.get_selection()
        selection.connect("changed", self.selectCardType)
	selection.set_select_function(self.cardviewSelectCb)

        sw = gtk.ScrolledWindow ()
        sw.set_policy (gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
	sw.set_shadow_type(gtk.SHADOW_IN)
        sw.add (self.cardview)
        box.pack_start (sw, gtk.TRUE)

        #Memory configuration menu
        hbox = gtk.HBox()
        hbox.set_border_width(3)
            
        label = gui.MnemonicLabel (_("_Video card RAM: "))

        self.ramOption = gtk.OptionMenu()
        label.set_mnemonic_widget(self.ramOption)
        self.ramOption.set_size_request (40, 20)
        self.ramMenu = gtk.Menu()

        for mem in self.videocard.possible_ram_sizes():
            if mem < 1000:
                tag = "%d KB" % (mem)
            else:
                tag = "%d MB" % (mem/1024)

            memitem = gtk.MenuItem(tag)
            self.ramMenu.add(memitem)

        hbox.pack_start(label, gtk.FALSE)
        hbox.pack_start(self.ramOption, gtk.TRUE, gtk.TRUE, 25)

        self.ramOption.set_menu (self.ramMenu)
        box.pack_start (hbox, gtk.FALSE)

        restore = gtk.Button (_("Restore _original values"))
        restore.connect ("clicked", self.restorePressed)
        hbox.pack_start(restore, gtk.FALSE, 25)
        
        self.skip = gtk.CheckButton (_("_Skip X configuration"))
        self.skip.connect ("toggled", self.skipToggled) 
        
        hbox = gtk.HBox (gtk.TRUE, 5)
        
        self.topbox = gtk.VBox (gtk.FALSE, 5)
        self.topbox.set_border_width (5)
        self.topbox.pack_start (box, gtk.TRUE, gtk.TRUE)
        self.topbox.pack_start (self.skip, gtk.FALSE)
        
        self.configbox = box
        
        self.skip.set_active (self.dispatch.stepInSkipList("monitor"))

        # set state
	self.ignoreEvents = 0
	self.currentMem = self.videocard.primaryCard(useProbed=0).getVideoRam()
	self.probedMem = self.videocard.primaryCard(useProbed=1).getVideoRam()
	self.setCurrent(self.currentCard, self.currentMem)

	setupTreeViewFixupIdleHandler(self.cardview, self.cardstore)

        return self.topbox
