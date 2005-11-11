#
# splashscreen.py: a quick splashscreen window that displays during ipl
#
# Matt Wilson <msw@redhat.com>
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

import os
os.environ["PYGTK_DISABLE_THREADS"] = "1"
os.environ["GNOME_DISABLE_CRASH_DIALOG"] = "1"

# we only want to enable the accessibility stuff if requested for now...
buf = open("/proc/cmdline").read()
if buf.find("dogtail") != -1:
    os.environ["GTK_MODULES"] = "gail:atk-bridge"

import gtk
from flags import flags

splashwindow = None

def splashScreenShow():
    from gui import readImageFromFile
    
    root = gtk.gdk.get_default_root_window()
    cursor = gtk.gdk.Cursor(gtk.gdk.LEFT_PTR)
    root.set_cursor(cursor)

    global splashwindow
    
    width = gtk.gdk.screen_width()
    p = None

    # If the xserver is running at 800x600 res or higher, use the
    # 800x600 splash screen.
    if width >= 800:
        p = readImageFromFile("pixmaps/first.png", dither = 1)
    else:
        p = readImageFromFile("pixmaps/first-lowres.png", dither = 1)        
                        
    if p:
        splashwindow = gtk.Window()
        def no_delete (window, event):
            return True
        splashwindow.connect('delete-event', no_delete)
        splashwindow.set_decorated(False)
        splashwindow.set_position(gtk.WIN_POS_CENTER)
        box = gtk.EventBox()
        box.modify_bg(gtk.STATE_NORMAL, box.get_style().white)
        box.add(p)
        splashwindow.add(box)
        box.show_all()
        splashwindow.show_now()
        gtk.gdk.flush()
        while gtk.events_pending():
            gtk.main_iteration(False)

def splashScreenPop():
    global splashwindow
    if splashwindow:
        splashwindow.destroy()
