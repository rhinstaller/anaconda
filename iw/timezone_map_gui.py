#
# timezone_map_gui.py: gui timezone map widget.
#
# Copyright 2001-2002 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import gobject
import pango
import gtk
try:
    import gnomecanvas
except ImportError:
    import gnome.canvas as gnomecanvas
import string
import re
import math
from rhpl.translate import _

class Enum:
    def __init__(self, *args):
        i = 0
        for arg in args:
            self.__dict__[arg] = i
            i += 1

class TimezoneMap(gtk.VBox):
    # force order of destruction for a few items.
    def __del__(self):
        del self.arrow
        del self.markers
        del self.current
    
    def __init__(self, zonetab, default="America/New_York",
                 map='/usr/share/anaconda/pixmaps/map480.png'):
        gtk.VBox.__init__(self, False, 5)

        # set up class member objects
        self.zonetab = zonetab
        self.markers = {}
        self.highlightedEntry = None

        # set up the map canvas
        self.canvas = gnomecanvas.Canvas()
        root = self.canvas.root()
        tpixbuf = gtk.gdk.pixbuf_new_from_file(map)

        # make it fit on screen for 640x480
        wid = tpixbuf.get_width()
        ht  = tpixbuf.get_height()
        if gtk.gdk.screen_width() <= 640 and wid > 375:
            newwid = 375
            newht = int((float(newwid)/float(wid))*float(ht))
            pixbuf = tpixbuf.scale_simple(newwid, newht, gtk.gdk.INTERP_BILINEAR)
        else:
            pixbuf = tpixbuf
                                
        self.mapWidth = pixbuf.get_width()
        self.mapHeight = pixbuf.get_height()

        root.add(gnomecanvas.CanvasPixbuf, x=0, y=0, pixbuf=pixbuf)
        x1, y1, x2, y2 = root.get_bounds()
        self.canvas.set_scroll_region(x1, y1, x2, y2)
        self.canvas.set_size_request(int(x2), int(y2))
        self.pack_start(self.canvas, False, False)

        self.current = root.add(gnomecanvas.CanvasText, text='x',
                                fill_color='red', anchor=gtk.ANCHOR_CENTER,
                                weight=pango.WEIGHT_BOLD)
        
        root.connect("event", self.mapEvent)
        self.canvas.connect("event", self.canvasEvent)

        self.arrow = root.add(gnomecanvas.CanvasLine,
                              fill_color='limegreen',
                              width_pixels=2,
                              first_arrowhead=False,
                              last_arrowhead=True,
                              arrow_shape_a=4.0,
                              arrow_shape_b=8.0,
                              arrow_shape_c=4.0,
                              points=(0.0, 0.0, 0.0, 0.0))
        self.arrow.hide()

        # set up status bar
        self.status = gtk.Statusbar()
        self.status.set_has_resize_grip(False)
        self.statusContext = self.status.get_context_id("")
        self.pack_start(self.status, False, False)

        self.columns = Enum("TZ", "COMMENTS", "ENTRY")
        
        # set up list of timezones
        self.listStore = gtk.ListStore(gobject.TYPE_STRING,
                                       gobject.TYPE_STRING,
                                       gobject.TYPE_PYOBJECT)
        
        for entry in zonetab.getEntries():
            iter = self.listStore.append()
            self.listStore.set_value(iter, self.columns.TZ, _(entry.tz))
            if entry.comments:
                self.listStore.set_value(iter, self.columns.COMMENTS,
                                         _(entry.comments))
            else:
                self.listStore.set_value(iter, self.columns.COMMENTS, "")
            self.listStore.set_value(iter, self.columns.ENTRY, entry)
            
            x, y = self.map2canvas(entry.lat, entry.long)
            marker = root.add(gnomecanvas.CanvasText, x=x, y=y,
                              text=u'\u00B7', fill_color='yellow',
                              anchor=gtk.ANCHOR_CENTER,
                              weight=pango.WEIGHT_BOLD)
            self.markers[entry.tz] = marker
            if entry.tz == default:
                self.currentEntry = entry

        self.listStore.set_sort_column_id(self.columns.TZ, gtk.SORT_ASCENDING)

        self.listView = gtk.TreeView(self.listStore)
        selection = self.listView.get_selection()
        selection.connect("changed", self.selectionChanged)
        self.listView.set_property("headers-visible", True)
        col = gtk.TreeViewColumn(_("_Location"), gtk.CellRendererText(), text=0)
        self.listView.append_column(col)
        col = gtk.TreeViewColumn(_("Description"), gtk.CellRendererText(), text=1)
        self.listView.append_column(col)

        sw = gtk.ScrolledWindow ()
        sw.add(self.listView)
        sw.set_shadow_type(gtk.SHADOW_IN)
        self.pack_start(sw, True, True)

        self.setCurrent(self.currentEntry)

    def getCurrent(self):
        return self.currentEntry

    def selectionChanged(self, selection, *args):
        (model, iter) = selection.get_selected()
        if iter is None:
            return
        entry = self.listStore.get_value(iter, self.columns.ENTRY)
        self.setCurrent(entry, skipList=1)

    def mapEvent(self, widget, event=None):
        if event.type == gtk.gdk.MOTION_NOTIFY:
            x1, y1 = self.canvas.root().w2i(event.x, event.y)
            lat, long = self.canvas2map(x1, y1)
            last = self.highlightedEntry
            self.highlightedEntry = self.zonetab.findNearest(lat, long)
            if last != self.highlightedEntry:
                self.status.pop(self.statusContext)
                status = _(self.highlightedEntry.tz)
                if self.highlightedEntry.comments:
                    status = "%s - %s" % (status,
                                          _(self.highlightedEntry.comments))
                self.status.push(self.statusContext, status)

            x2, y2 = self.map2canvas(self.highlightedEntry.lat,
                                       self.highlightedEntry.long)
            self.arrow.set(points=(x1, y1, x2, y2))
            self.arrow.show()
        elif event.type == gtk.gdk.BUTTON_PRESS:
            if event.button == 1:
                self.setCurrent(self.highlightedEntry)
                
    def setCurrent(self, entry, skipList=0):
        self.markers[self.currentEntry.tz].show()
        self.currentEntry = entry
        self.markers[self.currentEntry.tz].hide()
        x, y = self.map2canvas(self.currentEntry.lat, self.currentEntry.long)
        self.current.set(x=x, y=y)

        if skipList:
            return

        iter = self.listStore.get_iter_first()
        while iter:
            if self.listStore.get_value(iter, self.columns.ENTRY) == self.currentEntry:
                selection = self.listView.get_selection()
                selection.unselect_all()
                selection.select_iter(iter)
                path = self.listStore.get_path(iter)
                col = self.listView.get_column(0)
                self.listView.scroll_to_cell(path, col, True, 0.5, 0.5)
                self.listView.set_cursor(path, col, False)
                break
            iter = self.listStore.iter_next(iter)
        
    def canvasEvent(self, widget, event=None):
        if event.type == gtk.gdk.LEAVE_NOTIFY:
            self.arrow.hide()
            self.status.push(self.statusContext, "")            
        
    def map2canvas(self, lat, long):
        x2 = self.mapWidth
        y2 = self.mapHeight
        x = x2 / 2.0 + (x2 / 2.0) * long / 180.0
        y = y2 / 2.0 - (y2 / 2.0) * lat / 90.0
        return (x, y)

    def canvas2map(self, x, y):
        x2 = self.mapWidth
        y2 = self.mapHeight
        long = (x - x2 / 2.0) / (x2 / 2.0) * 180.0
        lat = (y2 / 2.0 - y) / (y2 / 2.0) * 90.0
        return (lat, long)

class ZoneTabEntry:
    def __init__(self, code=None, lat=0, long=0, tz=None, comments=None):
        self.code = code
        self.lat = lat
        self.long = long
        self.tz = tz
        self.comments = comments

class ZoneTab:
    def __init__(self, fn='/usr/share/zoneinfo/zone.tab'):
        self.entries = []
        self.readZoneTab(fn)

    def getEntries(self):
        return self.entries

    def findEntryByTZ(self, tz):
        for entry in self.entries:
            if entry.tz == tz:
                return entry
        # this has always been broken like this.  at least we're compatibly
        # broken now.
        return self.findEntryByTZ("America/New_York")

    def findNearest(self, lat, long):
        nearestEntry = None
        min = -1
        for entry in self.entries:
            dx = entry.long - long
            dy = entry.lat - lat
            dist = (dy * dy) + (dx * dx)
            if dist < min or min == -1:
                min = dist
                nearestEntry = entry
        return nearestEntry

    def convertCoord(self, coord, type="lat"):
        if type != "lat" and type != "long":
            raise TypeError, "invalid coord type"
        if type == "lat":
            deg = 3
        else:
            deg = 4
        degrees = string.atoi(coord[0:deg])
        order = len(coord[deg:])
        minutes = string.atoi(coord[deg:])
        if degrees > 0:
            return degrees + minutes/math.pow(10, order)
        return degrees - minutes/math.pow(10, order)
        
    def readZoneTab(self, fn):
        f = open(fn, 'r')
        comment = re.compile("^#")
        coordre = re.compile("[\+-]")
        while 1:
            line = f.readline()
            if not line:
                break
            if comment.search(line):
                continue
            fields = string.split(line, '\t')
            if len(fields) < 3:
                continue
            code = fields[0]
            split = coordre.search(fields[1], 1)
            lat = self.convertCoord(fields[1][:split.end() - 1], "lat")
            long = self.convertCoord(fields[1][split.end() - 1:], "long")
            tz = string.strip(fields[2])
            if len(fields) > 3:
                comments = string.strip(fields[3])
            else:
                comments = None
            entry = ZoneTabEntry(code, lat, long, tz, comments)
            self.entries.append(entry)

if __name__ == "__main__":
    zonetab = ZoneTab()
    win = gtk.Window()
    win.connect('destroy', gtk.mainquit)
    map = TimezoneMap(zonetab, map='../pixmaps/map480.png')
    vbox = gtk.VBox()
    vbox.pack_start(map)
    button = gtk.Button("Quit")
    button.connect("pressed", gtk.mainquit)
    vbox.pack_start(button, False, False)
    win.add(vbox)
    win.show_all()
    gtk.main()
    
