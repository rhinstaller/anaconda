#
# timezone_gui.py: gui timezone selection.
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

import string
import iutil
import gtk
from timezone_map_gui import TimezoneMap, ZoneTab
from iw_gui import *
from translate import _

class TimezoneWindow (InstallWindow):
    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        ics.setTitle (_("Time Zone Selection"))
        ics.setNextEnabled (1)
        ics.readHTML ("timezone")
        self.old_page = 0
        self.old_ulist_row = 9 # default to UTC row
        self.old_use_dst = 0

	self.timeZones = ((("-14", ""), ("Etc/GMT-14", "Etc/GMT-14")),
                          (("-13", ""), ("Etc/GMT-13", "Etc/GMT-13")),
                          (("-12", ""), ("Etc/GMT-12", "Etc/GMT-12")),
                          (("-11", ""), ("Etc/GMT-11", "Etc/GMT-11")),
                          (("-10", ""), ("Etc/GMT-10", "Etc/GMT-10")),
                          (("-09", ""), ("Etc/GMT-9", "Etc/GMT-9")),
                          (("-08", "US Pacific"),  ("Etc/GMT-8", "America/Los_Angeles")),
                          (("-07", "US Mountain"), ("Etc/GMT-7", "America/Denver")),
                          (("-06", "US Central"),  ("Etc/GMT-6", "America/Chicago")),
                          (("-05", "US Eastern"),  ("Etc/GMT-5", "America/New_York")),
                          (("-04", ""), ("Etc/GMT-4", "Etc/GMT-4")),
                          (("-03", ""), ("Etc/GMT-3", "Etc/GMT-3")),
                          (("-02", ""), ("Etc/GMT-2", "Etc/GMT-2")),
                          (("-01", ""), ("Etc/GMT-1", "Etc/GMT-1")),
                          (("",       ""), ("Etc/GMT", "Etc/GMT")),
                          (("+01", ""), ("Etc/GMT+1", "Etc/GMT+1")),
                          (("+02", ""), ("Etc/GMT+2", "Etc/GMT+2")),
                          (("+03", ""), ("Etc/GMT+3", "Etc/GMT+3")),
                          (("+04", ""), ("Etc/GMT+4", "Etc/GMT+4")),
                          (("+05", ""), ("Etc/GMT+5", "Etc/GMT+5")),
                          (("+06", ""), ("Etc/GMT+6", "Etc/GMT+6")),
                          (("+07", ""), ("Etc/GMT+7", "Etc/GMT+7")),
                          (("+08", ""), ("Etc/GMT+8", "Etc/GMT+8")),
                          (("+09", ""), ("Etc/GMT+9", "Etc/GMT+9")),
                          (("+10", ""), ("Etc/GMT+10", "Etc/GMT+10")),
                          (("+11", ""), ("Etc/GMT+11", "Etc/GMT+11")),
                          (("+12", ""), ("Etc/GMT+12", "Etc/GMT+12")))                    

    def getNext (self):
        self.old_page = self.nb.get_current_page ()
        self.timezone.utcOffset = self.nb.get_current_page ()
        self.timezone.dst = self.daylightCB.get_active ()
        
        if self.old_page == 0:
            newzone = self.tz.getCurrent().tz
            self.timezone.setTimezoneInfo (newzone, self.systemUTC.get_active ())
        else:
            timezone = self.timeZones[self.ulist.selection[0]][1]
            if self.daylightCB.get_active ():
                timezone = timezone[1]
            else:
                timezone = timezone[0]
            self.timezone.setTimezoneInfo (timezone, self.systemUTC.get_active ())

        return None

    def copy_toggled (self, cb1, cb2):
        if cb1.get_data ("toggling"): return
        
        cb2.set_data ("toggling", 1)
        cb2.set_active (cb1.get_active ())
        cb2.set_data ("toggling", 0)

    def view_change (self, widget, *args):
        if not self.tz.getCurrent():
            self.ics.setNextEnabled (gtk.FALSE)
        else:
            self.ics.setNextEnabled (gtk.TRUE)

    def setcurrent (self, widget, area):
        try:
            self.tz.setcurrent (self.default)
        except SystemError:
            self.default = _(self.langDefault)
            try:
                self.tz.setcurrent (self.default)
            except:
                pass
        widget.disconnect (self.id)

    # TimezoneWindow tag="timezone"
    def getScreen (self, instLang, timezone):
	self.timezone = timezone

        try:
            f = open ("/usr/share/anaconda/pixmaps/map480.png")
            f.close ()
        except:
            path = "gnome-map/map480.png"
        else:
            path = "/usr/share/anaconda/pixmaps/map480.png"
        
	nb = gtk.Notebook ()
        self.nb = nb

        mainBox = gtk.VBox (gtk.FALSE, 5)

        zonetab = ZoneTab()
        self.tz = TimezoneMap(zonetab=zonetab, map=path)

	(self.default, asUTC, asArc) = self.timezone.getTimezoneInfo()
        entry = zonetab.findEntryByTZ(self.default)
        if entry:
            self.tz.setCurrent(entry)

        self.old_page = timezone.utcOffset
        self.old_use_dst = timezone.dst
        self.langDefault = instLang.getDefaultTimeZone()
        if self.old_page:
            i = 0
            for ((offset, descr), (file, daylight)) in self.timeZones:
                if self.default == daylight or self.default == file:
                    break
                i = i + 1
            self.old_ulist_row = i
	if self.default:
            self.default = _(self.default)
	else:
            self.default = _(self.langDefault)
	    asUTC = 0

        if (string.find (self.default, "UTC") != -1):
            # self.default = _("America/New_York")
            self.default = "America/New_York"

        self.nb.connect ("realize", lambda widget, self=self:
                         self.nb.set_current_page (self.old_page))

        systemUTCCopy = gtk.CheckButton (_("System clock uses UTC"))
        self.systemUTC = gtk.CheckButton (_("System clock uses UTC"))

        systemUTCCopy.connect ("toggled", self.copy_toggled, self.systemUTC)
        self.systemUTC.connect ("toggled", self.copy_toggled, systemUTCCopy)

        self.systemUTC.set_active (asUTC)

        hbox = gtk.HBox(gtk.FALSE, 5)
        align = gtk.Alignment (0.5, 0.5)
        align.add (self.systemUTC)
        hbox.pack_start (align, gtk.FALSE)

        pix = self.ics.readPixmap ("timezone.png")
        if pix:
            a = gtk.Alignment ()
            a.add (pix)
            a.set (1.0, 0.0, 0.0, 0.0)
            hbox.pack_start (a, gtk.TRUE)
        
        mainBox.pack_start(hbox, gtk.FALSE)
        mainBox.pack_start(self.tz, gtk.TRUE, gtk.TRUE)
        mainBox.set_border_width (5)
       	nb.append_page (mainBox, gtk.Label (_("Location")))
        
        # set up page 2
	tzBox = gtk.VBox (gtk.FALSE)
        sw = gtk.ScrolledWindow ()
        sw.set_policy (gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
	self.ulist = gtk.CList (2)
        self.ulist.connect ("expose-event", lambda widget, area, self=self:
                            self.ulist.moveto (self.old_ulist_row))
        self.ulist.set_selection_mode (gtk.SELECTION_BROWSE)
        self.ulist.freeze ()
        for zone in self.timeZones:
            self.ulist.append (("UTC%s" % (zone[0][0],), zone[0][1]))
        self.ulist.columns_autosize ()
        self.ulist.thaw ()
        self.ulist.select_row (self.old_ulist_row, 0)
        sw.add (self.ulist)
        tzBox.pack_start (sw)
        box = gtk.HBox (gtk.FALSE)
        align = gtk.Alignment (0.5, 0.5)
        self.daylightCB = gtk.CheckButton (_("Use Daylight Saving Time (US only)"))
        self.daylightCB.set_active (self.old_use_dst)
        align.add (self.daylightCB)
        box.pack_start (align, gtk.FALSE)

        align = gtk.Alignment (1.0, 0.5)
        align.add (systemUTCCopy)

        box.pack_start (align, gtk.TRUE)
        tzBox.pack_start (box, gtk.FALSE)
        tzBox.set_border_width (5)
        self.tzBox = tzBox

        nb.append_page (tzBox, gtk.Label (_("UTC Offset")))

        def switch_page (widget, page, page_num, self=self):
            if page_num == 1:
                self.ics.setNextEnabled (gtk.TRUE)
            else:
                self.view_change (None)
                
        nb.connect ("switch_page", switch_page)
        
        box = gtk.VBox (gtk.FALSE, 5)
        box.pack_start (nb)
#        self.systemUTC = gtk.CheckButton (_("System clock uses UTC"))
#        self.systemUTC.set_active (asUTC)
#        align = gtk.Alignment (0, 0)
#        align.add (self.systemUTC)
#        box.pack_start (align, gtk.FALSE)
        box.set_border_width (5)

        return box

