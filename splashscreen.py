#
# splashscreen.py: a quick splashscreen window that displays during ipl
#
# Matt Wilson <msw@redhat.com>
#
# Copyright 2001 Red Hat, Inc.
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
os.environ["PYGTK_FATAL_EXCEPTIONS"] = "1"
os.environ["GNOME_DISABLE_CRASH_DIALOG"] = "1"

import gtk
from flags import flags

splashwindow = None

def splashScreenShow(configFileData):
    #set the background to a dark gray
    if flags.setupFilesystems:
        path = ("/usr/X11R6/bin/xsetroot",)
        args = ("-solid", "gray45")

        child = os.fork()
        if (child == 0):
            os.execv(path[0], path + args)
        try:
            pid, status = os.waitpid(child, 0)
        except OSError, (errno, msg):
            print __name__, "waitpid:", msg

    root = gtk.gdk.get_default_root_window()
    cursor = gtk.gdk.Cursor(gtk.gdk.LEFT_PTR)
    root.set_cursor(cursor)

    def load_image(file):
        p = gtk.Image()
        pixbuf = gtk.gdk.pixbuf_new_from_file("/usr/share/anaconda/" + file)
        if pixbuf is None:
            pixbuf = gtk.gdk.pixbuf_new_from_file(file)
        if pixbuf:
            p.set_from_pixbuf(pixbuf)
        return p

    global splashwindow
    
    width = gtk.gdk.screen_width()
    p = None

    # If the xserver is running at 800x600 res or higher, use the
    # 800x600 splash screen.
    if width >= 800:
        image = configFileData["Splashscreen"]

        p = load_image(image)
    else:
        p = load_image('pixmaps/first-lowres.png')
                        
    if p:
        splashwindow = gtk.Window()
        splashwindow.set_position(gtk.WIN_POS_CENTER)
        box = gtk.EventBox()
        box.modify_bg(gtk.STATE_NORMAL, box.get_style().white)
        box.add(p)
        splashwindow.add(box)
        box.show_all()
        splashwindow.show_now()
        gtk.gdk.flush()
        while gtk.events_pending():
            gtk.main_iteration(gtk.FALSE)

def splashScreenPop():
    global splashwindow
    if splashwindow:
        splashwindow.destroy()
