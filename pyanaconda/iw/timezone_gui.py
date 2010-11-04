#
# timezone_gui.py: gui timezone selection.
#
# Copyright (C) 2000, 2001, 2002, 2003, 2004, 2005, 2006  Red Hat, Inc.
# All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import string
import gtk
import gtk.glade
from scdate.core import zonetab

from timezone_map_gui import TimezoneMap
from iw_gui import *
from pyanaconda.bootloader import hasWindows

from pyanaconda.constants import *
import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

class TimezoneWindow(InstallWindow):
    def __init__(self, ics):
        InstallWindow.__init__(self, ics)

        # Need to set the custom handler before loading the glade file or
        # this won't work.
        gtk.glade.set_custom_handler(self.custom_widget_handler)

        # Set the default now.  We'll fix it for real in upon the first render.
        self.default = "America/New York"

        self.zonetab = zonetab.ZoneTab()

        # Pull in a bunch of widgets.
        self.xml = gtk.glade.XML("/usr/share/system-config-date/system-config-date.glade", domain="system-config-date")
        self.vbox = self.xml.get_widget("tz_vbox")
        self.utcCheckbox = self.xml.get_widget("utc_check")
        self.notebook = self.xml.get_widget("notebook")

        ics.setTitle(_("Time Zone Selection"))
        ics.setNextEnabled(1)

    def custom_widget_handler(self, xml, function_name, widget_name, str1, str2,
                              int1, int2):
        if hasattr(self, function_name):
            handler = getattr(self, function_name)
            return handler(str1, str2, int1, int2)
        else:
            # Lame.
            return gtk.Label()

    def timezone_widget_create (self, str1, str2, int1, int2):
        mappath = "/usr/share/system-config-date/pixmaps/map1440.png"

        self.tz = TimezoneMap(self.zonetab, self.default, map=mappath,
                              viewportWidth=480)
        self.tz.show_all()
        return self.tz

    def getNext(self):
        newzone = self.tz.getCurrent().tz
        self.timezone.setTimezoneInfo(newzone.replace(" ", "_"), self.utcCheckbox.get_active())
        return None

    # TimezoneWindow tag="timezone"
    def getScreen(self, anaconda):
	self.intf = anaconda.intf        
        self.timezone = anaconda.timezone
        (self.default, asUTC) = self.timezone.getTimezoneInfo()

        if not self.default:
            self.default = anaconda.instLanguage.getDefaultTimeZone(anaconda.rootPath)
            asUTC = 0

        if (string.find(self.default, "UTC") != -1):
            self.default = "America/New_York"

        self.default = self.default.replace("_", " ")

        self.utcCheckbox.set_active(asUTC)

        if not anaconda.ksdata:
            self.utcCheckbox.set_active(not hasWindows(anaconda.bootloader))

        self.notebook.remove(self.vbox)
        return self.vbox

    def renderCallback(self):
        # Now fix the default we set when we made the timezone map widget. Due
        # to a GTK weirdness, this would not do what we desire if put in
        # getScreen(): the element would get selected but stay outside of the
        # visible part of the TreeView.
        self.tz.setCurrent(self.zonetab.findEntryByTZ(self.default))
