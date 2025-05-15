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

import gi

import pyanaconda.core.timer

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")

import functools
import queue
import threading
import time
from contextlib import contextmanager

from gi.repository import Gdk, Gtk

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core import glib
from pyanaconda.core.async_utils import async_action_wait, run_in_loop
from pyanaconda.core.constants import (
    NOTICEABLE_FREEZE,
    PASSWORD_HIDE,
    PASSWORD_HIDE_ICON,
    PASSWORD_SHOW,
    PASSWORD_SHOW_ICON,
)
from pyanaconda.threading import AnacondaThread, threadMgr

log = get_module_logger(__name__)

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

    run_in_loop(wrap, args)


def fire_gtk_action(func, *args):
    """Run some Gtk action in the main thread and wait for it."""

    @async_action_wait
    def gtk_action():
        return func(*args)

    return gtk_action()


def gtk_batch_map(action, items, args=(), pre_func=None, batch_size=1):
    """
    Function that maps an action on items in a way that makes the action run in
    the main thread, but without blocking the main thread for a noticeable
    time. If a pre-processing function is given it is mapped on the items first
    before the action happens in the main thread.

    .. DANGER::
       MUST NOT BE CALLED NOR WAITED FOR FROM THE MAIN THREAD.

    :param action: any action that has to be done on the items in the main
                   thread
    :type action: (action_item, \\*args) -> None
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

    def preprocess(queue_instance):
        if pre_func:
            for item in items:
                queue_instance.put(pre_func(item))
        else:
            for item in items:
                queue_instance.put(item)

        queue_instance.put(TERMINATOR)

    def process_one_batch(arguments):
        (queue_instance, action, done_event) = arguments
        tstamp_start = time.time()
        tstamp = time.time()

        # process as many batches as user shouldn't notice
        while tstamp - tstamp_start < NOTICEABLE_FREEZE:
            for _i in range(batch_size):
                try:
                    action_item = queue_instance.get_nowait()
                    if action_item is TERMINATOR:
                        # all items processed, tell we are finished and return
                        done_event.set()
                        return False
                    else:
                        # run action on the item
                        action(action_item, *args)
                except queue.Empty:
                    # empty queue_instance, reschedule to run later
                    return True

            tstamp = time.time()

        # out of time but something left, reschedule to run again later
        return True

    item_queue_instance = queue.Queue()
    done_event = threading.Event()

    # we don't want to log the whole list, type and address is enough
    log.debug("Starting applying %s on %s", action, object.__repr__(items))

    # start a thread putting preprocessed items into the queue_instance
    threadMgr.add(AnacondaThread(prefix="AnaGtkBatchPre",
                                 target=preprocess,
                                 args=(item_queue_instance,)))

    run_in_loop(process_one_batch, (item_queue_instance, action, done_event))
    done_event.wait()
    log.debug("Finished applying %s on %s", action, object.__repr__(items))


def timed_action(delay=300, threshold=750, busy_cursor=True):
    """
    Function returning decorator for decorating often repeated actions that need
    to happen in the main loop (entry/slider change callbacks, typically), but
    that may take a long time causing the GUI freeze for a noticeable time.

    The return value of the decorator function returned by this function--i.e.,
    the value of timed_action()(function_to_be_decorated)--is an instance of
    the TimedAction class, which besides being callable provides a run_now
    method to shortcut the timer and run the action immediately. run_now will
    also be run in the main loop.

    If timed_action is used to decorate a method of a class, the decorated
    method will actually be a functools.partial instance. In this case, the
    TimedAction instance is accessible as the "func" property of the decorated
    method. Note that the func property will not have self applied.

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
            self._timer = None

            self._instance_map = {}

        @property
        def timer_active(self):
            """Whether there is a pending timer for this action."""
            return self._timer is not None

        def _run_once_one_arg(self, arguments):
            (args, kwargs) = arguments
            # run the function and clear stored values
            self._func(*args, **kwargs)
            self._last_start = None
            self._timer = None
            if busy_cursor:
                unbusyCursor()

            # function run, no need to schedule it again (return True would do)
            return False

        @async_action_wait
        def run_now(self, *args, **kwargs):
            # Remove the old timer
            if self._timer:
                self._timer.cancel()
                self._timer = None

            # Run the function immediately
            self._run_once_one_arg((args, kwargs))

        def __call__(self, *args, **kwargs):
            # get timestamps from the first or/and current run
            self._last_start = self._last_start or time.time()
            tstamp = time.time()

            if self._timer:
                # remove the old timer scheduling the function
                self._timer.cancel()
                self._timer = None

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

            self._timer = pyanaconda.core.timer.Timer()
            self._timer.timeout_msec(delay, self._run_once_one_arg, (args, kwargs))

        # This method is used by python to bind a class attribute to an
        # instance of that class, so in the case of functions this is what
        # converts a regular function into an instance method. Bind to the
        # instance of whatever is being decorated by returning a curried version
        # of ourself with the instance applied as the first argument.
        def __get__(self, instance, owner):
            if instance not in self._instance_map:
                self._instance_map[instance] = functools.partial(self, instance)

            return self._instance_map[instance]

    # Return TimedAction as the decorator function. The constructor will be
    # called with the function to be decorated as the argument, returning a
    # TimedAction instance as the decorated function, and TimedAction.__call__
    # will be used for the calls to the decorated function.
    return TimedAction


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
    provider.load_from_data(bytes("@binding-set IgnoreEscape {"
                                  "   unbind 'Escape';"
                                  "}"
                                  "GtkDialog { gtk-key-bindings: IgnoreEscape }",
                                  "utf-8"))

    context = dlg.get_style_context()
    context.add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


def setViewportBackground(vp, color="@theme_bg_color"):
    """Set the background color of the GtkViewport vp to be the same as the
       overall UI background.  This should not be called for every viewport,
       as that will affect things like TreeViews as well.
    """

    provider = Gtk.CssProvider()
    provider.load_from_data(bytes("viewport { background: %s }" % color, "utf-8"))
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

    This function converts the value to a string before passing to GLib function.
    """

    return glib.markup_escape_text(str(value))


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


def find_first_child(parent, match_func):
    """
    Find the first child widget of a container matching the given function.

    This method performs a breadth-first search for the widget. match_func
    takes the widget as a paramter, and the return value will be evaulated as
    a bool.

    :param GtkContainer parent: the container to search
    :param function match_func: The function defining the condition to match
    :return: The first matching widget
    :rtype: GtkWidget or None
    """
    search_list = parent.get_children()

    while search_list:
        # Pop off the first widget, test it, and add its children to the end
        widget = search_list.pop()
        if match_func(widget):
            return widget
        if isinstance(widget, Gtk.Container):
            search_list.extend(widget.get_children())

    return None


_widget_watch_list = {}


def watch_children(widget, callback, user_data=None):
    """
    Call callback on widget and all children of widget as they are added.

    Callback is a function that takes widget and user_data as arguments. No
    return value is expected.

    Callback will be called immediately for widget, and, if widget is a
    GtkContainer, for all children of widget. If widget is a container it will
    be then be watched for new widgets added to the container, and callback
    will be called on the new children as they are added.

    :param GtkWidget widget: the widget to watch
    :param function callback: the callback function
    :param user_data: optional user_data to pass to callback
    """

    # Watch new children as they are added, and unwatch them as they are removed
    def _add_signal(container, widget, user_data):
        callback, user_data = user_data

        watch_children(widget, callback, user_data)

    def _remove_signal(container, widget, user_data):
        callback, user_data = user_data

        unwatch_children(widget, callback, user_data)

    callback(widget, user_data)
    if isinstance(widget, Gtk.Container):
        for child in widget.get_children():
            watch_children(child, callback, user_data)

        # Watch for changes to the container
        # Only register new signals if there are not already signals for this
        # widget, function, data combo.
        signal_key = (widget, callback, user_data)

        if signal_key not in _widget_watch_list:
            add_signal = widget.connect("add", _add_signal, (callback, user_data))
            remove_signal = widget.connect("remove", _remove_signal, (callback, user_data))

            _widget_watch_list[signal_key] = (add_signal, remove_signal)


def unwatch_children(widget, callback, user_data=None):
    """
    Unregister a callback previously added with watch_children.

    :param GtkWidget widget: the widget to unwatch
    :param function callback: the callback that was previously added to the widget
    :param user_data: the user_data that was previously added to the widget
    """

    signal_key = (widget, callback, user_data)

    if signal_key in _widget_watch_list:
        add_signal, remove_signal = _widget_watch_list[signal_key]
        widget.disconnect(add_signal)
        widget.disconnect(remove_signal)
        del _widget_watch_list[signal_key]

    if isinstance(widget, Gtk.Container):
        for child in widget.get_children():
            unwatch_children(child, callback, user_data)


def set_password_visibility(entry, visible):
    """Make the password in/visible."""
    position = Gtk.EntryIconPosition.SECONDARY

    if visible:
        icon = PASSWORD_HIDE_ICON
        text = PASSWORD_HIDE
    else:
        icon = PASSWORD_SHOW_ICON
        text = PASSWORD_SHOW

    entry.set_visibility(visible)
    entry.set_icon_from_icon_name(position, icon)
    entry.set_icon_tooltip_text(position, text)
