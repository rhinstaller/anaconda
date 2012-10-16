# Miscellaneous UI functions
#
# Copyright (C) 2012  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Chris Lumens <clumens@redhat.com>
#
from contextlib import contextmanager
from gi.repository import Gdk, Gtk, GLib
import Queue

def gtk_call_once(func, *args):
    """Wrapper for GLib.idle_add call that ensures the func is called
       only once.
    """ 
    def wrap(args):
        func(*args)
        return False
    
    GLib.idle_add(wrap, args)

def gtk_thread_wait(func):
    """Decorator method which causes every call of the decorated function
       to be executed in the context of Gtk main loop and returns the ret
       value after the decorated method finishes.

       Method decorated by this decorator must not be called from inside
       of the Gtk main loop. It will cause a hang.
    """
    queue = Queue.Queue()

    def _idle_method(q_args):
        """This method contains the code for the main loop to execute.
        """
        queue, args = q_args
        ret = func(*args)
        queue.put(ret)
        return False

    def _call_method(*args):
        """The new body for the decorated method. It uses closure bound
           queue variable which is valid until the reference to this method
           is destroyed."""
        GLib.idle_add(_idle_method, (queue, args))
        return queue.get()

    return _call_method


def gtk_thread_nowait(func):
    """Decorator method which causes every call of the decorated function
       to be executed in the context of Gtk main loop. The new method does
       not wait for the callback to finish.
    """

    def _idle_method(args):
        """This method contains the code for the main loop to execute.
        """
        ret = func(*args)
        return False

    def _call_method(*args):
        """The new body for the decorated method.
        """
        GLib.idle_add(_idle_method, args)

    return _call_method


@contextmanager
def enlightbox(mainWindow, dialog):
    from gi.repository import AnacondaWidgets
    lightbox = AnacondaWidgets.lb_show_over(mainWindow)
    dialog.set_transient_for(lightbox)
    yield
    lightbox.destroy()

def setViewportBackground(vp, color="@theme_bg_color"):
    """Set the background color of the GtkViewport vp to be the same as the
       overall UI background.  This should not be called for every viewport,
       as that will affect things like TreeViews as well.
    """

    provider = Gtk.CssProvider()
    provider.load_from_data("GtkViewport { background-color: %s }" % color)
    context = vp.get_style_context()
    context.add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
