from gtk import *
from iw import *
import string
from gnome.ui import GnomeCanvas
from gui import _

import timezonemap

class Map (GnomeCanvas):
    def __init__ (self, map):
        self._o = map

class List (GtkScrolledWindow):
    def __init__ (self, list):
        self._o = list

class Status (GtkStatusbar):
    def __init__ (self, bar):
        self._o = bar

class Option (GtkOptionMenu):
    def __init__ (self, option):
        self._o = option

class TimezoneWindow (InstallWindow):

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        ics.setTitle (_("Time Zone Selection"))
        ics.setNextEnabled (1)
        ics.readHTML ("timezone")
        self.old_page = 0
        self.old_ulist_row = 15 # default to UTC row
        self.old_use_dst = 0

	self.timeZones = ((("-12:00", ""), ("UTC-12:00", "UTC-12:00")),
                          (("-11:00", ""), ("UTC-11:00", "UTC-11:00")),
                          (("-10:00", ""), ("UTC-10:00", "UTC-10:00")),
                          (("-09:30", ""), ("UTC-09:30", "UTC-09:30")),
                          (("-09:00", ""), ("UTC-09:00", "UTC-09:00")),
                          (("-08:30", ""), ("UTC-08:30", "UTC-08:30")),
                          (("-08:00", "US Pacific"),  ("UTC-08:00", "America/Los_Angeles")),
                          (("-07:00", "US Mountain"), ("UTC-07:00", "America/Denver")),
                          (("-06:00", "US Central"),  ("UTC-06:00", "America/Chicago")),
                          (("-05:00", "US Eastern"),  ("UTC-05:00", "America/New_York")),
                          (("-04:00", ""), ("UTC-04:00", "UTC-04:00")),
                          (("-03:30", ""), ("UTC-03:30", "UTC-03:30")),
                          (("-03:00", ""), ("UTC-03:00", "UTC-03:00")),
                          (("-02:00", ""), ("UTC-02:00", "UTC-02:00")),
                          (("-01:00", ""), ("UTC-01:00", "UTC-01:00")),
                          (("",       ""), ("UTC", "UTC")),
                          (("+01:00", ""), ("UTC+01:00", "UTC+01:00")),
                          (("+02:00", ""), ("UTC+02:00", "UTC+02:00")),
                          (("+03:00", ""), ("UTC+03:00", "UTC+03:00")),
                          (("+03:30", ""), ("UTC+03:30", "UTC+03:30")),
                          (("+04:00", ""), ("UTC+04:00", "UTC+04:00")),
                          (("+04:30", ""), ("UTC+04:30", "UTC+04:30")),
                          (("+05:00", ""), ("UTC+05:00", "UTC+05:00")),
                          (("+05:30", ""), ("UTC+05:30", "UTC+05:30")),
                          (("+06:00", ""), ("UTC+06:00", "UTC+06:00")),
                          (("+06:30", ""), ("UTC+06:30", "UTC+06:30")),
                          (("+07:00", ""), ("UTC+07:00", "UTC+07:00")),
                          (("+08:00", ""), ("UTC+08:00", "UTC+08:00")),
                          (("+09:00", ""), ("UTC+09:00", "UTC+09:00")),
                          (("+09:30", ""), ("UTC+09:30", "UTC+09:30")),
                          (("+10:00", ""), ("UTC+10:00", "UTC+10:00")),
                          (("+10:30", ""), ("UTC+10:30", "UTC+10:30")),
                          (("+11:00", ""), ("UTC+11:00", "UTC+11:00")),
                          (("+11:30", ""), ("UTC+11:30", "UTC+11:30")),
                          (("+12:00", ""), ("UTC+12:00", "UTC+12:00")),
                          (("+13:00", ""), ("UTC+13:00", "UTC+13:00")),
                          (("+14:00", ""), ("UTC+14:00", "UTC+14:00")))
                    

    def getNext (self):
	if not self.__dict__.has_key('list'): return None

        self.old_page = self.nb.get_current_page ()
        self.old_ulist_row = self.ulist.selection[0]
        self.old_use_dst = self.daylightCB.get_active ()
        
        if (self.old_page == 0):
            self.todo.setTimezoneInfo (self.list.get_text (self.list.selection[0], 0),
                                       self.systemUTC.get_active ())
        else:
            timezone = self.timeZones[self.ulist.selection[0]][1]
            if self.daylightCB.get_active ():
                timezone = timezone[1]
            else:
                timezone = timezone[0]
            self.todo.setTimezoneInfo (timezone, self.systemUTC.get_active ())

        return None

    def copy_toggled (self, cb1, cb2):
        if cb1.get_data ("toggling"): return
        
        cb2.set_data ("toggling", 1)
        cb2.set_active (cb1.get_active ())
        cb2.set_data ("toggling", 0)

    def view_change (self, widget, *args):
        if not self.list.selection:
            self.ics.setNextEnabled (FALSE)
        else:
            self.ics.setNextEnabled (TRUE)

    def getScreen (self):
        try:
            f = open ("/usr/share/anaconda/map480.png")
            f.close ()
        except:
            path = "gnome-map/map480.png"
        else:
            path = "/usr/share/anaconda/map480.png"
        
	nb = GtkNotebook ()
        self.nb = nb

        mainBox = GtkVBox (FALSE, 5)

        tz = timezonemap.new (path)
        self.tz = tz
        map = Map (tz.map)
        swList = List (tz.citylist)
        self.list = swList.children ()[0]

	rc = self.todo.getTimezoneInfo()
	if rc:
	    (self.default, asUTC, asArc) = rc
	else:
	    self.default = "America/New_York"
	    asUTC = 0

        if (string.find (self.default, "UTC") != -1):
            self.default = "America/New_York"

        self.list.connect ("draw", lambda widget, area, self=self: 
                           self.tz.setcurrent (self.default))
        self.nb.connect ("realize", lambda widget, self=self:
                         self.nb.set_page (self.old_page))

        status = Status (tz.statusbar)
        views = Option (tz.views)


        for menu_item in views.get_menu ().children ():
            menu_item.connect ("activate", self.view_change)

	# fix for current map weirdness in dr mike's code.
	views.get_menu ().children ()[0].activate ()

        label = GtkLabel (_("View:"))
        hbox = GtkHBox (FALSE, 5)
        hbox.pack_start (label, FALSE)
        align = GtkAlignment (0.5, 0.5)
        align.add (views)
        hbox.pack_start (align, FALSE)
        self.p1_align = align

        systemUTCCopy = GtkCheckButton (_("System clock uses UTC"))
        self.systemUTC = GtkCheckButton (_("System clock uses UTC"))

        systemUTCCopy.connect ("toggled", self.copy_toggled, self.systemUTC)
        self.systemUTC.connect ("toggled", self.copy_toggled, systemUTCCopy)

        self.systemUTC.set_active (asUTC)

        align = GtkAlignment (0.5, 0.5)
        align.add (self.systemUTC)
        hbox.pack_start (align, FALSE)

        im = self.ics.readPixmap ("timezone.png")
        if im:
            im.render ()
            pix = im.make_pixmap ()
            a = GtkAlignment ()
            a.add (pix)
            a.set (1.0, 0.0, 0.0, 0.0)
            hbox.pack_start (a, TRUE)
        
        frame = GtkFrame ()
        frame.set_shadow_type (SHADOW_IN)
        frame.add (map)
        
        mainBox.pack_start (hbox, FALSE)
        box = GtkVBox (FALSE, 0)
        box.pack_start (frame, FALSE)
        box.pack_start (status, FALSE)
        mainBox.pack_start (box, FALSE)
        mainBox.pack_start (swList, TRUE)

	tzBox = GtkVBox (FALSE)
        sw = GtkScrolledWindow ()
        sw.set_policy (POLICY_AUTOMATIC, POLICY_AUTOMATIC)
	self.ulist = GtkCList (2)
        self.ulist.connect ("draw", lambda widget, area, self=self:
                            self.ulist.moveto (self.old_ulist_row))
        self.ulist.set_selection_mode (SELECTION_BROWSE)
        self.ulist.freeze ()
        for zone in self.timeZones:
            self.ulist.append (("UTC%s" % (zone[0][0],), zone[0][1]))
        self.ulist.columns_autosize ()
        self.ulist.thaw ()
        self.ulist.select_row (self.old_ulist_row, 0)
        sw.add (self.ulist)
        tzBox.pack_start (sw)
        box = GtkHBox (FALSE)
        align = GtkAlignment (0.5, 0.5)
        self.daylightCB = GtkCheckButton (_("Use Daylight Saving Time (US only)"))
        self.daylightCB.set_active (self.old_use_dst)
        align.add (self.daylightCB)
        box.pack_start (align, FALSE)

        align = GtkAlignment (1.0, 0.5)
        align.add (systemUTCCopy)

        box.pack_start (align, TRUE)
        tzBox.pack_start (box, FALSE)
        tzBox.set_border_width (5)
        self.tzBox = tzBox

        mainBox.set_border_width (5)
	nb.append_page (mainBox, GtkLabel (_("Location")))
        nb.append_page (tzBox, GtkLabel (_("UTC Offset")))

        def switch_page (widget, page, page_num, self=self):
            if page_num == 1:
                self.ics.setNextEnabled (TRUE)
            else:
                self.view_change (None)
                
        nb.connect ("switch_page", switch_page)
        self.list.connect ("select_row", self.view_change)
        
        box = GtkVBox (FALSE, 5)
        box.pack_start (nb)
#        self.systemUTC = GtkCheckButton (_("System clock uses UTC"))
#        self.systemUTC.set_active (asUTC)
#        align = GtkAlignment (0, 0)
#        align.add (self.systemUTC)
#        box.pack_start (align, FALSE)
        box.set_border_width (5)

        return box

