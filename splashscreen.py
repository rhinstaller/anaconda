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

from gtk import *
from gtk import _root_window
import GDK
import GdkImlib

splashwindow = None

def splashScreenShow():
    root = _root_window ()
    cursor = cursor_new (GDK.LEFT_PTR)
    root.set_cursor (cursor)

    def load_image(file):
        try:
            im = GdkImlib.Image("/usr/share/anaconda/pixmaps/" + file)
        except:
            try:
                im = GdkImlib.Image("pixmaps/" + file)
            except:
                print "Unable to load", file

        return im

    global splashwindow
    
    width = screen_width()
    im = None

    # If the xserver is running at 800x600 res or higher, use the
    # 800x600 splash screen.
    if width >= 800:
        im = load_image('first.png')
    else:
        im = load_image('first-lowres.png')
                        
    if im:
        im.render ()
        splashwindow = GtkWindow ()
        splashwindow.set_position (WIN_POS_CENTER)
        box = GtkEventBox ()
        pix = im.make_pixmap ()
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
