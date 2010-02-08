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
import gtk.gdk
import gobject
from scdate.core import zonetab
import pango
import sys

from timezone_map_gui import TimezoneMap, Enum
from iw_gui import *
from booty.bootloaderInfo import dosFilesystems
from bootloader import hasWindows

from constants import *
import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

try:
    import gnomecanvas
except ImportError:
    import gnome.canvas as gnomecanvas

class TimezoneWindow(InstallWindow):
    def __init__(self, ics):
        InstallWindow.__init__(self, ics)

        # Need to set the custom handler before loading the glade file or
        # this won't work.
        gtk.glade.set_custom_handler(self.custom_widget_handler)

        # Set the default now.  We'll fix it for real in getScreen.
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

        self.tz = AnacondaTZMap(self.zonetab, self.default, map=mappath,
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

        # Now fix the default we set when we made the timezone map widget.
        self.tz.setCurrent(self.zonetab.findEntryByTZ(self.default))
        self.utcCheckbox.set_active(asUTC)

        if not anaconda.ksdata:
            self.utcCheckbox.set_active(not hasWindows(anaconda.bootloader))

        self.notebook.remove(self.vbox)
        return self.vbox

class AnacondaTZMap(TimezoneMap):
    def __init__(self, zonetab, default, map="", viewportWidth=480):
        TimezoneMap.__init__(self, zonetab, default, map=map, viewportWidth=viewportWidth)
        self.columns = Enum("TRANSLATED", "TZ", "ENTRY")

    def status_bar_init(self):
        self.status = None

    def load_entries (self, root):
        iter = self.tzStore.get_iter_first()

        for entry in self.zonetab.getEntries():
            if entry.lat is not None and entry.long is not None:
                x, y = self.map2canvas(entry.lat, entry.long)
                marker = root.add(gnomecanvas.CanvasText, x=x, y=y,
                                  text=u'\u00B7', fill_color='yellow',
                                  anchor=gtk.ANCHOR_CENTER,
                                  weight=pango.WEIGHT_BOLD)
                self.markers[entry.tz] = marker

                if entry.tz == "America/New York":
                    # In case the /etc/sysconfig/clock is messed up, use New
                    # York as the default.
                    self.fallbackEntry = entry

            iter = self.tzStore.insert_after(iter, [gettext.ldgettext("system-config-date", entry.tz), entry.tz, entry])

    def timezone_list_init (self, default):
        self.hbox = gtk.HBox()
        self.tzStore = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING,
                                     gobject.TYPE_PYOBJECT)

        root = self.canvas.root()

        self.load_entries(root)

        # Add the ListStore to the sorted model after the list has been
        # populated, since otherwise we end up resorting on every addition.
        self.tzSorted = gtk.TreeModelSort(self.tzStore)
        self.tzSorted.set_sort_column_id(0, gtk.SORT_ASCENDING)
        self.tzCombo = gtk.ComboBox(model=self.tzSorted)
        cell = gtk.CellRendererText()
        self.tzCombo.pack_start(cell, True)
        self.tzCombo.add_attribute(cell, 'text', 0)
        self.tzCombo.connect("changed", self.selectionChanged)
        self.hbox.pack_start(self.tzCombo, False, False)

        self.pack_start(self.hbox, False, False)

    def selectionChanged(self, widget, *args):
        iter = widget.get_active_iter()
        if iter is None:
            return
        entry = widget.get_model().get_value(iter, self.columns.ENTRY)
        if entry:
            self.setCurrent (entry, skipList=1)
            if entry.long != None and entry.lat != None:
                self.move_to (entry.long, entry.lat)

    def updateTimezoneList(self):
        # Find the currently selected item in the combo box and update both
        # the combo and the comment label.
        iter = self.tzCombo.get_model().get_iter_first()
        while iter:
            if self.tzCombo.get_model().get_value(iter, 1) == self.currentEntry.tz:
                self.tzCombo.set_active_iter(iter)
                break

            iter = self.tzCombo.get_model().iter_next(iter)
