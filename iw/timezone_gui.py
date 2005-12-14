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
import gtk
import gtk.glade
import gtk.gdk
import gui
import gobject
import zonetab
import pango
import sys

sys.path.append("/usr/share/system-config-date")

from timezone_map_gui import TimezoneMap
from rhpl.translate import _, textdomain
from iw_gui import *

try:
    import gnomecanvas
except ImportError:
    import gnome.canvas as gnomecanvas

textdomain("system-config-date")

class TimezoneWindow(InstallWindow):
    def __init__(self, ics):
        InstallWindow.__init__(self, ics)

        # Need to set the custom handler before loading the glade file or
        # this won't work.
        gtk.glade.set_custom_handler(self.custom_widget_handler)

        # Set the default now.  We'll fix it for real in getScreen.
        self.default = "America/New_York"

        self.zonetab = zonetab.ZoneTab()

        # Pull in a bunch of widgets.
        self.xml = gtk.glade.XML("/usr/share/system-config-date/system-config-date.glade"), domain="system-config-date")
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
        mappath = "/usr/share/system-config-date/pixmaps/map1440.png"
        regionspath = "/usr/share/system-config-date/regions"

        self.tz = AnacondaTZMap(self.zonetab, self.default, map=mappath,
                                regions=regionspath,
                                viewportWidth=gtk.gdk.screen_height())
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
        self.tz.setCurrent(self.zonetab.findEntryByTZ(self.default))

        self.notebook.remove(self.vbox)
        return self.vbox

# Only populate the combo box with cities that are in the zoom area or are
# currently selected.
def tzFilterFunc (model, iter, user_data):
    (longmin, latmin, longmax, latmax) = user_data.get_shown_region_long_lat()
    curlat = model.get_value(iter, 1)
    curlong = model.get_value(iter, 2)

    if curlat >= latmin and curlat <= latmax and curlong >= longmin and curlong <= longmax:
        return True
    elif user_data.currentEntry == None:
        if model.get_value(iter, 0) == "America/New_York":
            return True
        else:
            return False
    elif model.get_value(iter, 0) == user_data.currentEntry.tz:
        return True
    else:
        return False

class AnacondaTZMap(TimezoneMap):
    def status_bar_init(self):
        self.status = None

    def timezone_list_init (self):
        self.hbox = gtk.HBox()
        self.tzStore = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_INT, gobject.TYPE_INT)
        self.tzSorted = gtk.TreeModelSort(self.tzStore)
        self.tzSorted.set_sort_column_id(0, gtk.SORT_ASCENDING)
        self.tzFilter = self.tzSorted.filter_new()
        self.tzCombo = gtk.ComboBox(model=self.tzFilter)
        cell = gtk.CellRendererText()
        self.tzCombo.pack_start(cell, True)
        self.tzCombo.add_attribute(cell, 'text', 0)
        self.tzFilter.set_visible_func(tzFilterFunc, self)

        root = self.canvas.root()
        
        for entry in self.zonetab.getEntries():
            x, y = self.map2canvas(entry.lat, entry.long)
            marker = root.add(gnomecanvas.CanvasText, x=x, y=y,
                              text=u'\u00B7', fill_color='yellow',
                              anchor=gtk.ANCHOR_CENTER,
                              weight=pango.WEIGHT_BOLD)
            self.markers[entry.tz] = marker

            if entry.tz == "America/New_York":
                #In case the /etc/sysconfig/clock is messed up, use New York as default
                self.fallbackEntry = entry

            iter = self.tzStore.append()
            self.tzStore.set_value(iter, 0, entry.tz)
            self.tzStore.set_value(iter, 1, entry.lat)
            self.tzStore.set_value(iter, 2, entry.long)

        self.tzCombo.connect("changed", self.selectionChanged)
        self.hbox.pack_start(self.tzCombo, False, False)

        # Label for the comment (if there is one)
        self.commentLabel = gtk.Label()
        self.hbox.pack_start(self.commentLabel, True, True, padding=5)

        self.pack_start(self.hbox, False, False)

    def selectionChanged(self, widget, *args):
        iter = widget.get_active_iter()
        entry = self.zonetab.findEntryByTZ(widget.get_model().get_value(iter, 0))
        self.setCurrent(entry)

    def overviewPressEvent(self):
        TimezoneMap.overviewPressEvent()
        self.tzFilter.refilter()

    def zoomMoveEvent(self, event):
        x1, y1 = self.canvas.root ().w2i (event.x, event.y)
        long, lat = self.canvas2map (x1, y1)
        r = self.region
        longmin, latmin, longmax, latmax = self.get_shown_region_long_lat ()
        last = self.highlightedEntry
        self.highlightedEntry = self.zonetab.findNearest(long, lat, longmin, latmin, longmax, latmax)

        if self.highlightedEntry:
            x2, y2 = self.map2canvas(self.highlightedEntry.lat,
                                    self.highlightedEntry.long)
            self.arrow.set(points=(x1, y1, x2, y2))
            self.arrow.show ()
        else:
            self.arrow.hide ()

    def zoomPressEvent(self, event):
        TimezoneMap.zoomPressEvent(event)

        if event.button == 1:
            self.tzFilter.refilter()

    def updateTimezoneList(self):
        # Find the currently selected item in the combo box and update both
        # the combo and the comment label.
        iter = self.tzCombo.get_model().get_iter_first()
        while iter:
            if self.tzCombo.get_model().get_value(iter, 0) == self.currentEntry.tz:
                self.tzCombo.set_active_iter(iter)

                if self.currentEntry.comments != None:
                    self.commentLabel.set_text(self.currentEntry.comments)
                else:
                    self.commentLabel.set_text("")

                break
            iter = self.tzCombo.get_model().iter_next(iter)
