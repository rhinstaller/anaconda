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
from gi.repository import Gtk, GLib, AnacondaWidgets
import Queue
import gettext

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
        func(*args)
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
    # importing globally would cause a circular dependency
    from pyanaconda.ui.gui import ANACONDA_WINDOW_GROUP

    lightbox = AnacondaWidgets.Lightbox(parent_window=mainWindow)
    ANACONDA_WINDOW_GROUP.add_window(lightbox)
    dialog.set_transient_for(lightbox)
    yield
    lightbox.destroy()

def ignoreEscape(dlg):
    """Prevent a dialog from accepting the escape keybinding, which emits a
       close signal and will cause the dialog to close with some return value
       we are likely not expecting.  Instead, this method will cause the
       escape key to do nothing for the given GtkDialog.
    """
    provider = Gtk.CssProvider()
    provider.load_from_data("@binding-set IgnoreEscape {"
                            "   unbind 'Escape';"
                            "}"
                            "GtkDialog { gtk-key-bindings: IgnoreEscape }")

    context = dlg.get_style_context()
    context.add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

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

def really_hide(widget):
    """Some widgets need to be both hidden, and have no_show_all set on them
       to prevent them from being shown later when the screen is redrawn.
       This method takes care of that.
    """
    widget.set_no_show_all(True)
    widget.hide()

def really_show(widget):
    """Some widgets need to have no_show_all unset before they can also be
       shown, so they are displayed later when the screen is redrawn.  This
       method takes care of that.
    """
    widget.set_no_show_all(False)
    widget.show()

def set_treeview_selection(treeview, item, col=0):
    """
    Select the given item in the given treeview and scroll to it.

    :param treeview: treeview to select and item in
    :type treeview: GtkTreeView
    :param item: item to be selected
    :type item: str
    :param col: column to search for the item in
    :type col: int
    :return: selected iterator or None if item was not found
    :rtype: GtkTreeIter or None

    """

    model = treeview.get_model()
    itr = model.get_iter_first()
    while itr and not model[itr][col] == item:
        itr = model.iter_next(itr)

    if not itr:
        # item not found, cannot be selected
        return None

    # otherwise select the item and scroll to it
    selection = treeview.get_selection()
    selection.select_iter(itr)
    path = model.get_path(itr)

    # row_align=0.5 tells GTK to move the cell to the middle of the
    # treeview viewport (0.0 should align it with the top, 1.0 with bottom)
    # If the cell is the uppermost one, it should align it with the top
    # of the viewport.
    #
    # Unfortunately, this does not work as expected due to a bug in GTK.
    # (see rhbz#970048)
    treeview.scroll_to_cell(path, use_align=True, row_align=0.5)

    return itr

def get_default_widget_direction():
    """
    Function to get default widget direction (RTL/LTR) for the current language
    configuration.

    XXX: this should be provided by the Gtk itself (#1008821)

    :return: either Gtk.TextDirection.LTR or Gtk.TextDirection.RTL
    :rtype: GtkTextDirection

    """

    # this is quite a hack, but it's exactly the same check Gtk uses internally
    xlated = gettext.ldgettext("gtk30", "default:LTR")
    if xlated == "default:LTR":
        return Gtk.TextDirection.LTR
    else:
        return Gtk.TextDirection.RTL

def setup_gtk_direction():
    """
    Set the right direction (RTL/LTR) of the Gtk widget's and their layout based
    on the current language configuration.

    """

    Gtk.Widget.set_default_direction(get_default_widget_direction())
