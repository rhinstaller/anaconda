from gtk import *
from iw import *
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
        ics.setHTML ("<HTML><BODY>Select your current location</BODY></HTML>")

	self.timeZones = ("-12:00",
                          "-11:00",
                          "-10:00",
                          "-09:30",
                          "-09:00",
                          "-08:30",
                          "-08:00",
                          "-07:00",
                          "-06:00",
                          "-05:00",
                          "-04:00",
                          "-03:30",
                          "-03:00",
                          "-02:00",
                          "-01:00",
                          "",
                          "+01:00",
                          "+02:00",
                          "+03:00",
                          "+03:30",
                          "+04:00",
                          "+04:30",
                          "+05:00",
                          "+05:30",
                          "+06:00",
                          "+06:30",
                          "+07:00",
                          "+08:00",
                          "+09:00",
                          "+09:30",
                          "+10:00",
                          "+10:30",
                          "+11:00",
                          "+11:30",
                          "+12:00",
                          "+13:00",
                          "+14:00")
                    

    def getNext (self):
        self.todo.setTimezoneInfo (self.list.get_text (self.list.selection[0], 0),
                                   self.systemUTC.get_active ())
        return None

    def fixUp (self):
        self.tz.setcurrent (self.default)

    def getScreen (self):
        try:
            f = open ("/usr/share/anaconda/map480.png")
            f.close ()
        except:
            path = "gnome-map/map480.png"
        else:
            path = "/usr/share/anaconda/map480.png"
        
	nb = GtkNotebook ()

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

        status = Status (tz.statusbar)
        views = Option (tz.views)

        label = GtkLabel (_("View:"))
        hbox = GtkHBox (FALSE, 5)
        hbox.pack_start (label, FALSE)
        hbox.pack_start (views, FALSE)
        
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
	list = GtkCList (1)
        list.set_selection_mode (SELECTION_BROWSE)
        list.freeze ()
        for zone in self.timeZones:
            list.append (("UTC %s" % (zone,),))
        list.columns_autosize ()
        list.thaw ()
        list.select_row (15, 0)
        sw.add (list)
        tzBox.pack_start (sw)
        align = GtkAlignment (0, 0)
        daylightCB = GtkCheckButton (_("Use Daylight Saving Time"))
        align.add (daylightCB)
        tzBox.pack_start (align, FALSE)
        tzBox.set_border_width (5)
        

        mainBox.set_border_width (5)
	nb.append_page (mainBox, GtkLabel (_("Location")))
        nb.append_page (tzBox, GtkLabel (_("UTC Offset")))

        box = GtkVBox (FALSE, 5)
        box.pack_start (nb)
        self.systemUTC = GtkCheckButton (_("System clock uses UTC"))
        self.systemUTC.set_active (asUTC)
        align = GtkAlignment (0, 0)
        align.add (self.systemUTC)
        box.pack_start (align, FALSE)
        box.set_border_width (5)
        return box

