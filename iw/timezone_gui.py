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

import sys
sys.path.insert(0, "/mnt/source/RHupdates/system-config-date")

import string
import gtk
import gtk.glade
import gui
import gobject
from timezone_map_gui import TimezoneMap
from zonetab import *
from rhpl.translate import _, textdomain
from iw_gui import *

import logging
log = logging.getLogger("anaconda")

textdomain("system-config-date")

class TimezoneWindow(InstallWindow):
    def __init__(self, ics):
        InstallWindow.__init__(self, ics)

        # Need to set the custom handler before loading the glade file or
        # this won't work.
        gtk.glade.set_custom_handler(self.custom_widget_handler)

        # Set the default now.  We'll fix it for real in getScreen.
        self.default = "America/New_York"

        self.zonetab = ZoneTab()

        # Pull in a bunch of widgets.
        self.xml = gtk.glade.XML(gui.findGladeFile("system-config-date.glade"), domain="system-config-date")
        self.vbox = self.xml.get_widget("tz_vbox")
        self.utcCheckbox = self.xml.get_widget("utc_check")
        self.notebook = self.xml.get_widget("notebook")
        self.tzActionLabel = self.xml.get_widget("tzActionLabel")

        # Need to set this after we've pulled in the glade file.
        self.tz.tzActionLabel = self.tzActionLabel
        self.tz.setActionLabelToMap()

        ics.setTitle(_("Time Zone Selection"))
        ics.setNextEnabled(1)
        ics.readHTML("timezone")

    def custom_widget_handler(self, xml, function_name, widget_name, str1, str2,
                              int1, int2):
        if hasattr(self, function_name):
            handler = getattr(self, function_name)
            return handler(str1, str2, int1, int2)
        else:
            # Lame.
            return gtk.Label()

    def timezone_widget_create (self, str1, str2, int1, int2):
        mappath = "/mnt/source/RHupdates/system-config-date/pixmaps/map1440.png"
        regionspath = "/mnt/source/RHupdates/system-config-date/regions"

        self.tz = TimezoneMap(self.zonetab, self.default, map=mappath,
                              regions=regionspath)
        self.tz.show_all()
        return self.tz

    def getNext(self):
        newzone = self.tz.getCurrent().tz
        self.timezone.setTimezoneInfo(newzone, self.utcCheckbox.get_active())
        return None

    # TimezoneWindow tag="timezone"
    def getScreen(self, instLang, timezone):
        self.timezone = timezone
        (self.default, asUTC, asArc) = self.timezone.getTimezoneInfo()

        if not self.default:
            self.default = instLang.getDefaultTimeZone()
            asUTC = 0

        if (string.find(self.default, "UTC") != -1):
            self.default = "America/New_York"

        # Now fix the default we set when we made the timezone map widget.
        log.info("fixing up current entry")
        self.tz.setCurrent(self.zonetab.findEntryByTZ(self.default))

        self.notebook.remove(self.vbox)
        return self.vbox
