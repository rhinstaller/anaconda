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
        ics.setPrevEnabled (0)
        ics.setNextEnabled (1)
        ics.setHTML ("<HTML><BODY>Select your current location</BODY></HTML>")

    def getScreen (self):
        try:
            f = open ("/usr/share/anaconda/map480.png")
            f.close ()
        except:
            path = "gnome-map/map480.png"
        else:
            path = "/usr/share/anaconda/map480.png"
        
        mainBox = GtkVBox (FALSE, 0)
        tz = timezonemap.new ()
        map = Map (tz.map)
        list = List (tz.citylist)
        status = Status (tz.statusbar)
        views = Option (tz.views)

        label = GtkLabel (_("View"))
        hbox = GtkHBox (FALSE, 5)
        hbox.pack_start (label, FALSE)
        hbox.pack_start (views, FALSE)
        
        frame = GtkFrame ()
        frame.set_shadow_type (SHADOW_IN)
        frame.add (map)
        
        mainBox.pack_start (hbox, FALSE)
        mainBox.pack_start (frame, FALSE)
        mainBox.pack_start (status, FALSE)
        mainBox.pack_start (list, TRUE)
        return mainBox

