# Miscellaneous UI functions
#
# Copyright (C) 2012, 2013 Red Hat, Inc.
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
#                    Martin Sivak <msivak@redhat.com>
#                    Vratislav Podzimek <vpodzime@redhat.com>
#

from pyanaconda.threads import threadMgr

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

def gtk_action_wait(func):
    """Decorator method which ensures every call of the decorated function to be
       executed in the context of Gtk main loop even if called from a non-main
       thread and returns the ret value after the decorated method finishes.
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
        """The new body for the decorated method. If needed, it uses closure
           bound queue variable which is valid until the reference to this
           method is destroyed."""
        if threadMgr.in_main_thread():
            # nothing special has to be done in the main thread
            return func(*args)

        GLib.idle_add(_idle_method, (queue, args))
        return queue.get()

    return _call_method


def gtk_action_nowait(func):
    """Decorator method which ensures every call of the decorated function to be
       executed in the context of Gtk main loop even if called from a non-main
       thread. The new method does not wait for the callback to finish.
    """

    def _idle_method(args):
        """This method contains the code for the main loop to execute.
        """
        ret = func(*args)
        return False

    def _call_method(*args):
        """The new body for the decorated method.
        """
        if threadMgr.in_main_thread():
            # nothing special has to be done in the main thread
            func(*args)
            return

        GLib.idle_add(_idle_method, args)

    return _call_method


@contextmanager
def enlightbox(mainWindow, dialog):
    from pyanaconda.ui.gui import ANACONDA_WINDOW_GROUP
    from gi.repository import AnacondaWidgets
    lightbox = AnacondaWidgets.lb_show_over(mainWindow)
    ANACONDA_WINDOW_GROUP.add_window(lightbox)
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

def fancy_set_sensitive(widget, value):
    """Set the sensitivity of a widget, and then set the sensitivity of
       all widgets it is a mnemonic widget for.  This has the effect of
       marking both an entry and its label as sensitive/insensitive, for
       instance.
    """
    widget.set_sensitive(value)
    for w in widget.list_mnemonic_labels():
        w.set_sensitive(value)
