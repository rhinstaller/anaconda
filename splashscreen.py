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
#os.environ["GNOME_DISABLE_CRASH_DIALOG"] = "1"

from gtk import *
from gtk import _root_window
from flags import flags
import GDK
import gdkpixbuf

splashwindow = None

def splashScreenShow(configFileData):
    #set the background to a dark gray
    if flags.setupFilesystems:
        path = ("/usr/X11R6/bin/xsetroot",)
        args = ("-solid", "gray45")

        child = os.fork ()
        if (child == 0):
            os.execv (path[0], path + args)
        try:
            pid, status = os.waitpid(child, 0)
        except OSError, (errno, msg):
            print __name__, "waitpid:", msg

    root = _root_window ()
    cursor = cursor_new (GDK.LEFT_PTR)
    root.set_cursor (cursor)

    def load_image(file):
        try:
            p = gdkpixbuf.new_from_file("/usr/share/anaconda/" + file)
        except:
            try:
                p = gdkpixbuf.new_from_file("" + file)
            except:
                p = None
                print "Unable to load", file

        return p

    global splashwindow
    
    width = screen_width()
    p = None

    # If the xserver is running at 800x600 res or higher, use the
    # 800x600 splash screen.
    if width >= 800:
        image = configFileData["Splashscreen"]

        p = load_image(image)
    else:
        p = load_image('pixmaps/first-lowres.png')
                        
    if p:
        pix = apply (GtkPixmap, p.render_pixmap_and_mask())
        splashwindow = GtkWindow ()
        splashwindow.set_position (WIN_POS_CENTER)
        box = GtkEventBox ()
        style = box.get_style ().copy ()
        style.bg[STATE_NORMAL] = style.white
        box.set_style (style)
        box.add (pix)
        splashwindow.add (box)
        box.show_all()
        splashwindow.show_now()
        gdk_flush ()
        while events_pending ():
            mainiteration (FALSE)

def splashScreenPop():
    global splashwindow
    if splashwindow:
        splashwindow.destroy ()
