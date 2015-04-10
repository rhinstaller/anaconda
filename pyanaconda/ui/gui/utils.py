# Miscellaneous UI functions
#
# Copyright (C) 2012-2014 Red Hat, Inc.
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

from contextlib import contextmanager

from pyanaconda.threads import threadMgr, AnacondaThread

from pyanaconda.constants import NOTICEABLE_FREEZE
from gi.repository import Gdk, Gtk, GLib
import Queue
import time
import threading

import logging
log = logging.getLogger("anaconda")

# any better idea how to create a unique, distinguishable object that cannot be
# confused with anything else?
TERMINATOR = object()

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

def fire_gtk_action(func, *args):
    """Run some Gtk action in the main thread and wait for it."""

    @gtk_action_wait
    def gtk_action():
        return func(*args)

    return gtk_action()

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

class GtkActionList(object):
    """Class for scheduling Gtk actions to be all run at once."""

    def __init__(self):
        self._actions = []

    def add_action(self, func, *args):
        """Add Gtk action to be run later."""

        @gtk_action_wait
        def gtk_action():
            func(*args)

        self._actions.append(gtk_action)

    def fire(self):
        """Run all scheduled Gtk actions."""

        for action in self._actions:
            action()

        self._actions = []

def gtk_batch_map(action, items, args=(), pre_func=None, batch_size=1):
    """
    Function that maps an action on items in a way that makes the action run in
    the main thread, but without blocking the main thread for a noticeable
    time. If a pre-processing function is given it is mapped on the items first
    before the action happens in the main thread.

    MUST NOT BE CALLED NOR WAITED FOR FROM THE MAIN THREAD.

    :param action: any action that has to be done on the items in the main
                   thread
    :type action: (action_item, *args) -> None
    :param items: an iterable of items that the action should be mapped on
    :type items: iterable
    :param args: additional arguments passed to the action function
    :type args: tuple
    :param pre_func: a function that is mapped on the items before they are
                     passed to the action function
    :type pre_func: item -> action_item
    :param batch_size: how many items should be processed in one run in the main loop
    :raise AssertionError: if called from the main thread
    :return: None

    """

    assert(not threadMgr.in_main_thread())

    def preprocess(queue):
        if pre_func:
            for item in items:
                queue.put(pre_func(item))
        else:
            for item in items:
                queue.put(item)

        queue.put(TERMINATOR)

    def process_one_batch((queue, action, done_event)):
        tstamp_start = time.time()
        tstamp = time.time()

        # process as many batches as user shouldn't notice
        while tstamp - tstamp_start < NOTICEABLE_FREEZE:
            for _i in range(batch_size):
                try:
                    action_item = queue.get_nowait()
                    if action_item is TERMINATOR:
                        # all items processed, tell we are finished and return
                        done_event.set()
                        return False
                    else:
                        # run action on the item
                        action(action_item, *args)
                except Queue.Empty:
                    # empty queue, reschedule to run later
                    return True

            tstamp = time.time()

        # out of time but something left, reschedule to run again later
        return True

    item_queue = Queue.Queue()
    done_event = threading.Event()

    # we don't want to log the whole list, type and address is enough
    log.debug("Starting applying %s on %s", action, object.__repr__(items))

    # start a thread putting preprocessed items into the queue
    threadMgr.add(AnacondaThread(prefix="AnaGtkBatchPre",
                                 target=preprocess,
                                 args=(item_queue,)))

    GLib.idle_add(process_one_batch, (item_queue, action, done_event))
    done_event.wait()
    log.debug("Finished applying %s on %s", action, object.__repr__(items))

def timed_action(delay=300, threshold=750, busy_cursor=True):
    """
    Function returning decorator for decorating often repeated actions that need
    to happen in the main loop (entry/slider change callbacks, typically), but
    that may take a long time causing the GUI freeze for a noticeable time.

    :param delay: number of milliseconds to wait for another invocation of the
                  decorated function before it is actually called
    :type delay: int
    :param threshold: upper bound (in milliseconds) to wait for the decorated
                      function to be called from the first/last time
    :type threshold: int
    :param busy_cursor: whether the cursor should be made busy or not in the
                        meantime of the decorated function being invocated from
                        outside and it actually being called
    :type busy_cursor: bool

    """

    class TimedAction(object):
        """Class making the timing work."""

        def __init__(self, func):
            self._func = func
            self._last_start = None
            self._timer_id = None

        def _run_once_one_arg(self, (args, kwargs)):
            # run the function and clear stored values
            self._func(*args, **kwargs)
            self._last_start = None
            self._timer_id = None
            if busy_cursor:
                unbusyCursor()

            # function run, no need to schedule it again (return True would do)
            return False

        def run_func(self, *args, **kwargs):
            # get timestamps from the first or/and current run
            self._last_start = self._last_start or time.time()
            tstamp = time.time()

            if self._timer_id:
                # remove the old timer scheduling the function
                GLib.source_remove(self._timer_id)
                self._timer_id = None

            # are we over the threshold?
            if (tstamp - self._last_start) * 1000 > threshold:
                # over threshold, run the function right now and clear the
                # timestamp
                self._func(*args, **kwargs)
                self._last_start = None

            # schedule the function to be run later to allow additional changes
            # in the meantime
            if busy_cursor:
                busyCursor()
            self._timer_id = GLib.timeout_add(delay, self._run_once_one_arg,
                                              (args, kwargs))

    def decorator(func):
        """
        Decorator replacing the function with its timed version using an
        instance of the TimedAction class.

        :param func: the decorated function

        """

        ta = TimedAction(func)

        def inner_func(*args, **kwargs):
            ta.run_func(*args, **kwargs)

        return inner_func

    return decorator

@contextmanager
def blockedHandler(obj, func):
    """Prevent a GLib signal handling function from being called during some
       block of code.
    """
    obj.handler_block_by_func(func)
    yield
    obj.handler_unblock_by_func(func)

def busyCursor():
    window = Gdk.get_default_root_window()
    if not window:
        return

    window.set_cursor(Gdk.Cursor(Gdk.CursorType.WATCH))

def unbusyCursor():
    window = Gdk.get_default_root_window()
    if not window:
        return

    window.set_cursor(Gdk.Cursor(Gdk.CursorType.ARROW))

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

def setup_gtk_direction():
    """
    Set the right direction (RTL/LTR) of the Gtk widget's and their layout based
    on the current language configuration.

    """

    Gtk.Widget.set_default_direction(Gtk.get_locale_direction())

def escape_markup(value):
    """
    Escape strings for use within Pango markup.

    This function converts the value to a string before passing markup_escape_text().
    """

    if isinstance(value, unicode):
        value = value.encode("utf-8")

    escaped = GLib.markup_escape_text(str(value))

    return escaped.decode("utf-8")

# This will be populated by override_cell_property. Keys are tuples of (column, renderer).
# Values are a dict of the form {property-name: (property-func, property-data)}.
_override_cell_property_map = {}

def override_cell_property(tree_column, cell_renderer, propname, property_func, data=None):
    """
    Override a single property of a cell renderer.

    property_func takes the same arguments as GtkTreeCellDataFunc:
    (TreeViewColumn, CellRenderer, TreeModel, TreeIter, data). Instead of being
    expected to manipulate the CellRenderer itself, this method should instead
    return the value to which the property should be set.

    This method calls set_cell_data_func on the column and renderer.

    :param GtkTreeViewColumn column: the column to override
    :param GtkCellRenderer cell_renderer: the cell renderer to override
    :param str propname: the property to set on the renderer
    :param function property_func: a function that returns the value of the property to set
    :param data: Optional data to pass to property_func
    """

    def _cell_data_func(tree_column, cell_renderer, tree_model, tree_iter, _data=None):
        overrides = _override_cell_property_map[(tree_column, cell_renderer)]
        for property_name in overrides:
            property_func, property_func_data = overrides[property_name]
            property_value = property_func(tree_column, cell_renderer,
                    tree_model, tree_iter, property_func_data)
            cell_renderer.set_property(property_name, property_value)

    if (tree_column, cell_renderer) not in _override_cell_property_map:
        _override_cell_property_map[(tree_column, cell_renderer)] = {}
        tree_column.set_cell_data_func(cell_renderer, _cell_data_func)

    _override_cell_property_map[(tree_column, cell_renderer)][propname] = (property_func, data)
