#
# timezone_gui.py: gui timezone selection.
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

import string
import iutil
import gtk
import gobject
from timezone_map_gui import TimezoneMap, ZoneTab
from iw_gui import *
from rhpl.translate import _, textdomain

textdomain("redhat-config-date")

class TimezoneWindow(InstallWindow):
    def __init__(self, ics):
	InstallWindow.__init__(self, ics)

        ics.setTitle(_("Time Zone Selection"))
        ics.setNextEnabled(1)
        ics.readHTML("timezone")

    def getNext(self):
        newzone = self.tz.getCurrent().tz
        self.timezone.setTimezoneInfo(newzone, self.systemUTC.get_active())
        return None

    # TimezoneWindow tag="timezone"
    def getScreen(self, instLang, timezone):
	self.timezone = timezone

        try:
            f = open("/usr/share/anaconda/pixmaps/map480.png")
            f.close()
        except:
            path = "pixmaps/map480.png"
        else:
            path = "/usr/share/anaconda/pixmaps/map480.png"
        
        mainBox = gtk.VBox(gtk.FALSE, 5)

        zonetab = ZoneTab()
        self.tz = TimezoneMap(zonetab=zonetab, map=path)

	(self.default, asUTC, asArc) = self.timezone.getTimezoneInfo()

        self.langDefault = instLang.getDefaultTimeZone()

	if not self.default:
            self.default = self.langDefault
	    asUTC = 0

        if (string.find(self.default, "UTC") != -1):
            self.default = "America/New_York"

        self.tz.setCurrent(zonetab.findEntryByTZ(self.default))

        self.systemUTC = gtk.CheckButton(_("System clock uses _UTC"))
        self.systemUTC.set_active(asUTC)

        hbox = gtk.HBox(gtk.FALSE, 5)
        pix = self.ics.readPixmap("timezone.png")
        if pix:
            hbox.pack_start(pix, gtk.FALSE)
        
        hbox.pack_start(gtk.Label(_("Please select the nearest city in your timezone:")), gtk.FALSE)
        mainBox.pack_start(hbox, gtk.FALSE)
        mainBox.pack_start(self.tz, gtk.TRUE, gtk.TRUE)
        mainBox.pack_start(self.systemUTC, gtk.FALSE)
        mainBox.set_border_width(5)

        box = gtk.VBox(gtk.FALSE, 5)
        box.pack_start(mainBox)
        box.set_border_width(5)

        return box

