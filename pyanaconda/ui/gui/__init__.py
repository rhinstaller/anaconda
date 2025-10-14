# Base classes for the graphical user interface.
#
# Copyright (C) 2011-2012  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import inspect
import os
import site
import sys
from contextlib import contextmanager

import gi
import meh.ui.gui

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("AnacondaWidgets", "3.4")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("GObject", "2.0")
gi.require_version("GLib", "2.0")

import os.path

from gi.repository import AnacondaWidgets, Gdk, GdkPixbuf, GLib, GObject, Gtk

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core import constants, util
from pyanaconda.core.async_utils import async_action_wait
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import WINDOW_TITLE_TEXT
from pyanaconda.core.glib import Bytes, GError
from pyanaconda.core.i18n import C_, _
from pyanaconda.core.product import get_product_is_final_release
from pyanaconda.core.threads import thread_manager
from pyanaconda.flags import flags
from pyanaconda.keyboard import can_configure_keyboard
from pyanaconda.ui import UserInterface, common
from pyanaconda.ui.gui.helpers import autoinstall_stopped
from pyanaconda.ui.gui.utils import (
    really_hide,
    unbusyCursor,
    unwatch_children,
    watch_children,
)
from pyanaconda.ui.helpers import get_distribution_text

log = get_module_logger(__name__)

__all__ = ["GraphicalUserInterface", "QuitDialog"]

ANACONDA_WINDOW_GROUP = Gtk.WindowGroup()

# Stylesheet priorities to use for product-specific stylesheets.
# Custom stylesheets should be higher than our base stylesheet, and
# stylesheets from updates.img and product.img should be higher than that.  All
# levels should be lower than GTK_STYLE_PROVIDER_PRIORITY_USER.
STYLE_PROVIDER_PRIORITY_CUSTOM = Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 15
STYLE_PROVIDER_PRIORITY_UPDATES = Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 20
assert STYLE_PROVIDER_PRIORITY_UPDATES < Gtk.STYLE_PROVIDER_PRIORITY_USER


class GUIObject(common.UIObject):
    """This is the base class from which all other GUI classes are derived.  It
       thus contains only attributes and methods that are common to everything
       else.  It should not be directly instantiated.

       Class attributes:

       builderObjects   -- A list of UI object names that should be extracted from
                           uiFile and exposed for this class to use.  If this list
                           is empty, all objects will be exposed.

                           Only the following kinds of objects need to be exported:

                           (1) Top-level objects (like GtkDialogs) that are directly
                           used in Python.

                           (2) Top-level objects that are not directly used in
                           Python, but are used by another object somewhere down
                           in the hierarchy.  This includes things like a custom
                           GtkImage used by a button that is part of an exported
                           dialog, and a GtkListStore that is the model of a
                           Gtk*View that is part of an exported object.
       mainWidgetName   -- The name of the top-level widget this object
                           object implements.  This will be the widget searched
                           for in uiFile by the window property.
       focusWidgetName  -- The name of the widget to focus when the object is entered,
                           or None.
       uiFile           -- The location of an XML file that describes the layout
                           of widgets shown by this object.  UI files are
                           searched for relative to the same directory as this
                           object's module.
       translationDomain-- The gettext translation domain for the given GUIObject
                           subclass. By default the "anaconda" translation domain
                           is used, but external applications, such as Initial Setup,
                           that use GUI elements (Hubs & Spokes) from Anaconda
                           can override the translation domain with their own,
                           so that their subclasses are properly translated.
    """
    builderObjects = []
    mainWidgetName = None

    # Since many of the builder files do not define top-level widgets, the usual
    # {get,can,is,has}_{focus,default} properties don't work real good. Define the
    # widget to be focused in python, instead.
    focusWidgetName = None

    uiFile = ""
    translationDomain = "anaconda"

    def __init__(self, data):
        """Create a new UIObject instance, including loading its uiFile and
           all UI-related objects.

           Instance attributes:

           data     -- An instance of a pykickstart Handler object.  The Hub
                       never directly uses this instance.  Instead, it passes
                       it down into Spokes when they are created and applied.
                       The Hub simply stores this instance so it doesn't need
                       to be passed by the user.
           skipTo   -- If this attribute is set to something other than None,
                       it must be the name of a class (as a string).  Then,
                       the interface will skip to the first instance of that
                       class in the action list instead of going on to
                       whatever the next action is normally.

                       Note that actions may only skip ahead, never backwards.
                       Also, standalone spokes may not skip to an individual
                       spoke off a hub.  They can only skip to the hub
                       itself.
        """
        super().__init__(data)

        if self.__class__ is GUIObject:
            raise TypeError("GUIObject is an abstract class")

        self.skipTo = None
        self.applyOnSkip = False

        self.builder = Gtk.Builder()
        self.builder.set_translation_domain(self.translationDomain)
        self._window = None

        if self.builderObjects:
            self.builder.add_objects_from_file(self._findUIFile(), self.builderObjects)
        else:
            self.builder.add_from_file(self._findUIFile())

        self.builder.connect_signals(self)

        # Hide keyboard indicator if we can't configure the keyboard
        # It doesn't really give you any benefit of seeing something which could
        # give you wrong values.
        # This has to be applied to every spoke and hub - we have to ignore dialog and other
        # non full screen parts.
        if not can_configure_keyboard() and isinstance(self.window, AnacondaWidgets.BaseWindow):
            layout_indicator = self.window.get_layout_indicator_box()
            really_hide(layout_indicator)
            layout_indicator.set_sensitive(False)

    def _findUIFile(self):
        path = os.environ.get("UIPATH", "./:/usr/share/anaconda/ui/")
        dirs = path.split(":")

        # append the directory where this UIObject is defined
        dirs.append(os.path.dirname(inspect.getfile(self.__class__)))

        for d in dirs:
            testPath = os.path.join(d, self.uiFile)
            if os.path.isfile(testPath) and os.access(testPath, os.R_OK):
                return testPath

        raise OSError("Could not load UI file '{}' for object '{}'".format(self.uiFile, self))

    @property
    def window(self):
        """Return the object out of the GtkBuilder representation
           previously loaded by the load method.
        """

        # This will raise an AttributeError if the subclass failed to set a
        # mainWidgetName attribute, which is exactly what I want.
        if not self._window:
            self._window = self.builder.get_object(self.mainWidgetName)

        return self._window

    @property
    def main_window(self):
        """Return the top-level main window."""
        return MainWindow.get()

    def clear_info(self):
        """Clear any info bar from the bottom of the screen."""
        self.window.clear_info()

    def set_error(self, msg):
        """Display an info bar along the bottom of the screen with the provided
           message.  This method is used to display critical errors anaconda
           may not be able to do anything about, but that the user may.  A
           suitable background color and icon will be displayed.
        """
        self.window.set_error(msg)

    def set_info(self, msg):
        """Display an info bar along the bottom of the screen with the provided
           message.  This method is used to display informational text -
           non-critical warnings during partitioning, for instance.  The user
           should investigate these messages but doesn't have to.  A suitable
           background color and icon will be displayed.
        """
        self.window.set_info(msg)

    def set_warning(self, msg):
        """Display an info bar along the bottom of the screen with the provided
           message.  This method is used to display errors the user needs to
           attend to in order to continue installation.  This is the bulk of
           messages.  A suitable background color and icon will be displayed.
        """
        self.window.set_warning(msg)


class QuitDialog(GUIObject):
    builderObjects = ["quitDialog"]
    mainWidgetName = "quitDialog"
    uiFile = "main.glade"

    MESSAGE = ""

    def run(self):
        if self.MESSAGE:
            self.builder.get_object("quit_message").set_label(_(self.MESSAGE))
        rc = self.window.run()
        return rc


class ErrorDialog(GUIObject):
    builderObjects = ["errorDialog", "errorTextBuffer"]
    mainWidgetName = "errorDialog"
    uiFile = "main.glade"

    # pylint: disable=arguments-differ
    def refresh(self, msg):
        buf = self.builder.get_object("errorTextBuffer")
        buf.set_text(msg, -1)

    def run(self):
        rc = self.window.run()
        return rc


class MainWindow(Gtk.Window):
    """This is a top-level, full size window containing the Anaconda screens."""

    __instance = None

    @classmethod
    def get(cls):
        """Get the top-level main window.

        Return the latest instance of this class.

        :return MainWindow: the main window
        :raise ValueError: if the window doesn't exist
        """
        if not cls.__instance:
            raise ValueError("The main window doesn't exist!")

        return cls.__instance

    def __init__(self, fullscreen=False, decorated=False):
        """Create a new anaconda main window.

          :param bool fullscreen: if True, fullscreen the window, if false maximize
        """
        super().__init__()
        # Keep the latest main window.
        self.__class__.__instance = self

        # Remove the title bar, resize controls and other stuff if the window manager
        # allows it and decorated is set to False. Otherwise, it has no effect.
        self.set_decorated(decorated)
        self.set_titlebar(Gtk.DrawingArea())

        # Hide the titlebar when maximized if the window manager allows it.
        # This makes anaconda look full-screenish but without covering parts
        # needed to interact with the window manager, like the GNOME top bar.
        self.set_hide_titlebar_when_maximized(True)

        # The Anaconda and Initial Setup windows might sometimes get decorated with
        # a titlebar which contains the __init__.py header text by default.
        # As all Anaconda and Initial Setup usually have a very distinct title text
        # inside the window, the titlebar text is redundant and should be disabled.
        self.set_title(_(WINDOW_TITLE_TEXT))

        # Set the icon used in the taskbar of window managers that have a taskbar
        # The "org.fedoraproject.AnacondaInstaller" icon is part of fedora-logos
        self.set_icon_name("org.fedoraproject.AnacondaInstaller")

        # Treat an attempt to close the window the same as hitting quit
        self.connect("delete-event", self._on_delete_event)

        # Create a black, 50% opacity pixel that will be scaled to fit the lightbox overlay
        # The confusing list of unnamed parameters is:
        # bytes, colorspace (there is no other colorspace), has-alpha,
        # bits-per-sample (has to be 8), width, height,
        # rowstride (bytes between row starts, but we only have one row)
        self._transparent_base = GdkPixbuf.Pixbuf.new_from_bytes(Bytes.new([0, 0, 0, 127]),
                GdkPixbuf.Colorspace.RGB, True, 8, 1, 1, 1)

        # Contain everything in an overlay so the window can be overlayed with the transparency
        # for the lightbox effect
        self._overlay = Gtk.Overlay()
        self._overlay_img = None
        self._overlay.connect("get-child-position", self._on_overlay_get_child_position)

        self._overlay_depth = 0

        # Create a stack and a list of what's been added to the stack
        # Double the stack transition duration since the default 200ms is too
        # quick to get the point across
        self._stack = Gtk.Stack(transition_duration=400)
        self._stack_contents = set()

        # Create an accel group for the F12 accelerators added after window transitions
        self._accel_group = Gtk.AccelGroup()
        self.add_accel_group(self._accel_group)

        # Make the window big
        if fullscreen:
            self.fullscreen()
        else:
            self.maximize()

        self._overlay.add(self._stack)
        self.add(self._overlay)
        self.show_all()

        self._current_action = None

        # Help button mnemonics handling
        self._mnemonic_signal = None

        # Apply the initial language attributes
        self._language = None
        self.reapply_language()

    def _on_delete_event(self, widget, event, user_data=None):
        # Use the quit-clicked signal on the the current standalone, even if the
        # standalone is not currently displayed.
        if self.current_action:
            self.current_action.window.emit("quit-clicked")

        # Stop the window from being closed here
        return True

    def _on_overlay_get_child_position(self, overlay_container, overlayed_widget, _allocation, user_data=None):
        overlay_allocation = overlay_container.get_allocation()

        # Scale the overlayed image's pixbuf to the size of the GtkOverlay
        overlayed_widget.set_from_pixbuf(self._transparent_base.scale_simple(
            overlay_allocation.width, overlay_allocation.height, GdkPixbuf.InterpType.NEAREST))

        # Return False to indicate that the child allocation is not yet set
        return False

    def _on_child_added(self, widget, user_data):
        # If this is GtkLabel, apply the language attribute
        if isinstance(widget, Gtk.Label):
            AnacondaWidgets.apply_language(widget, user_data)

    @property
    def current_action(self):
        return self._current_action

    @property
    def current_window(self):
        """Return the window that is currently visible on the screen.

        Anaconda uses a window stack, so the currently visible window is the
        one on the top of the stack.
        """
        return self._stack.get_visible_child()

    def _setVisibleChild(self, child):
        # Remove the F12 accelerator from the old window
        old_screen = self._stack.get_visible_child()
        if old_screen:
            if self._accel_group.query(Gdk.KEY_F12, 0):
                old_screen.remove_accelerator(self._accel_group, Gdk.KEY_F12, 0)
            if self._accel_group.query(Gdk.KEY_F1, 0):
                old_screen.remove_accelerator(self._accel_group, Gdk.KEY_F1, 0)
            if self._accel_group.query(Gdk.KEY_F1, Gdk.ModifierType.MOD1_MASK):
                old_screen.remove_accelerator(self._accel_group, Gdk.KEY_F1, Gdk.ModifierType.MOD1_MASK)

        # Check if the widget is already on the stack
        if child not in self._stack_contents:
            self._stack.add(child.window)
            self._stack_contents.add(child)
            child.window.show_all()

        # It would be handy for F12 to continue to work like it did in the old
        # UI, by skipping you to the next screen or sending you back to the hub
        if isinstance(child.window, AnacondaWidgets.BaseStandalone):
            child.window.add_accelerator("continue-clicked", self._accel_group,
                    Gdk.KEY_F12, 0, 0)
        elif isinstance(child.window, AnacondaWidgets.SpokeWindow):
            child.window.add_accelerator("button-clicked", self._accel_group,
                    Gdk.KEY_F12, 0, 0)

        self._stack.set_visible_child(child.window)

        if child.focusWidgetName:
            child.builder.get_object(child.focusWidgetName).grab_focus()

    def setCurrentAction(self, standalone):
        """Set the current standalone widget.

           This changes the currently displayed screen and, if the standalone
           is a hub, sets the hub as the screen to which spokes will return.

           :param AnacondaWidgets.BaseStandalone standalone: the new standalone action
        """
        # Slide the old hub/standalone off of the new one
        self._stack.set_transition_type(Gtk.StackTransitionType.UNDER_LEFT)

        self._current_action = standalone
        self._setVisibleChild(standalone)

    def enterSpoke(self, spoke):
        """Enter a spoke.

           The spoke will be displayed as the current screen, but the current-action
           to which the spoke will return will not be changed.

           :param AnacondaWidgets.SpokeWindow spoke: a spoke to enter
        """
        # Slide up, as if the spoke is under the hub
        self._stack.set_transition_type(Gtk.StackTransitionType.UNDER_UP)

        self._setVisibleChild(spoke)

    def returnToHub(self):
        """Exit a spoke and return to a hub."""
        # Slide back down over the spoke
        self._stack.set_transition_type(Gtk.StackTransitionType.OVER_DOWN)

        self._setVisibleChild(self._current_action)

    def lightbox_on(self):
        self._overlay_depth += 1
        if not self._overlay_img:
            # Add an overlay image that will be filled and scaled in get-child-position
            self._overlay_img = Gtk.Image()
            self._overlay_img.show_all()
            self._overlay.add_overlay(self._overlay_img)

    def lightbox_off(self):
        self._overlay_depth -= 1
        if self._overlay_depth == 0 and self._overlay_img:
            # Remove the overlay image
            self._overlay_img.destroy()
            self._overlay_img = None

    @contextmanager
    def enlightbox(self, dialog):
        """Display a dialog in a lightbox over the main window.

           :param GtkDialog: the dialog to display
        """
        self.lightbox_on()

        # Set the dialog as transient for ourself
        ANACONDA_WINDOW_GROUP.add_window(dialog)
        dialog.set_position(Gtk.WindowPosition.CENTER_ALWAYS)
        dialog.set_transient_for(self)

        # Apply the language attributes to the dialog
        watch_children(dialog, self._on_child_added, self._language)

        yield

        unwatch_children(dialog, self._on_child_added, self._language)

        self.lightbox_off()

    def reapply_language(self):
        # Set a new watch_children watcher with the current language

        # Clear the old one, if there is one
        if self._language:
            unwatch_children(self, self._on_child_added, self._language)

        self._language = os.environ["LANG"]
        watch_children(self, self._on_child_added, self._language)


class GraphicalUserInterface(UserInterface):
    """This is the standard GTK+ interface we try to steer everything to using.
       It is suitable for use both directly and via RDP.
    """
    def __init__(self, storage, payload,
                 distributionText=get_distribution_text,
                 isFinal=get_product_is_final_release(),
                 quitDialog=QuitDialog,
                 gui_lock=None,
                 fullscreen=False):

        super().__init__(storage, payload)

        self._actions = []
        self._currentAction = None
        self._gui_lock = gui_lock

        self.data = None

        if conf.system.provides_liveuser:
            GLib.set_prgname("liveinst")    # matches liveinst.desktop filename
        self.mainWindow = MainWindow(fullscreen=fullscreen, decorated=False)

        self._distributionText = distributionText
        self._isFinal = isFinal
        self._quitDialog = quitDialog
        self._mehInterface = GraphicalExceptionHandlingIface(
                                    self.mainWindow.lightbox_on)

        ANACONDA_WINDOW_GROUP.add_window(self.mainWindow)

    basemask = "pyanaconda.ui"
    basepath = os.path.dirname(os.path.dirname(__file__))
    sitepackages = [os.path.join(dir, "pyanaconda", "ui")
                    for dir in site.getsitepackages()]
    pathlist = set([basepath] + sitepackages)

    _categories = []
    _spokes = []
    _hubs = []

    # as list comprehension can't reference class level variables in Python 3 we
    # need to use a for cycle (http://bugs.python.org/issue21161)
    for path in pathlist:
        _categories.append((basemask + ".categories.%s", os.path.join(path, "categories")))
        _spokes.append((basemask + ".gui.spokes.%s", os.path.join(path, "gui/spokes")))
        _hubs.append((basemask + ".gui.hubs.%s", os.path.join(path, "gui/hubs")))

    paths = UserInterface.paths + {
        "categories": _categories,
        "spokes": _spokes,
        "hubs": _hubs,
    }

    def _widgetScale(self):
        # First, check if the GDK_SCALE environment variable is already set. If so,
        # leave it alone.
        if "GDK_SCALE" in os.environ:
            log.debug("GDK_SCALE already set to %s, not scaling", os.environ["GDK_SCALE"])
            return

        # Next, check if a scaling factor is already being applied via XSETTINGS,
        # such as by gnome-settings-daemon
        display = Gdk.Display.get_default()
        screen = display.get_default_screen()
        val = GObject.Value()
        val.init(GObject.TYPE_INT)
        if screen.get_setting("gdk-window-scaling-factor", val):
            log.debug("Window scale set to %s by XSETTINGS, not scaling", val.get_int())
            return

        # Get the primary monitor dimensions in pixels and mm from Gdk
        primary_monitor = display.get_primary_monitor()

        # It can be None if no primary monitor is configured by the user.
        if not primary_monitor:
            return

        monitor_geometry = primary_monitor.get_geometry()
        monitor_scale = primary_monitor.get_scale_factor()
        monitor_width_mm = primary_monitor.get_width_mm()
        monitor_height_mm = primary_monitor.get_height_mm()

        # Sometimes gdk returns 0 for physical widths and heights
        if monitor_height_mm == 0 or monitor_width_mm == 0:
            return

        # Check if this monitor is high DPI, using heuristics from gnome-settings-dpi.
        # If the monitor has a height >= 1200 pixels and a resolution > 192 dpi in both
        # x and y directions, apply a scaling factor of 2 so that anaconda isn't all tiny
        monitor_width_px = monitor_geometry.width * monitor_scale
        monitor_height_px = monitor_geometry.height * monitor_scale
        monitor_dpi_x = monitor_width_px / (monitor_width_mm / 25.4)
        monitor_dpi_y = monitor_height_px / (monitor_height_mm / 25.4)

        log.debug("Detected primary monitor: %dx%d %ddpix %ddpiy", monitor_width_px,
                monitor_height_px, monitor_dpi_x, monitor_dpi_y)
        if monitor_height_px >= 1200 and monitor_dpi_x > 192 and monitor_dpi_y > 192:
            display.set_window_scale(2)
            # Export the scale so that Gtk programs launched by anaconda are also scaled
            util.setenv("GDK_SCALE", "2")

    @property
    def tty_num(self):
        return 6

    @property
    def meh_interface(self):
        return self._mehInterface

    def _list_hubs(self):
        """Return a list of Hub classes to be imported to this interface"""
        from pyanaconda.ui.gui.hubs.summary import SummaryHub
        return [SummaryHub]

    def _is_standalone(self, obj):
        """Is the spoke passed as obj standalone?"""
        from pyanaconda.ui.gui.spokes import StandaloneSpoke
        return isinstance(obj, StandaloneSpoke)

    def _is_standalone_class(self, cls):
        """Is the class passed as cls standalone?"""
        from pyanaconda.ui.gui.spokes import StandaloneSpoke
        return issubclass(cls, StandaloneSpoke)

    def setup(self, data):
        self._actions = self.getActionClasses(self._list_hubs())
        self.data = data

    def getActionClasses(self, hubs):
        """Grab all relevant standalone spokes, add them to the passed
           list of hubs and order the list according to the
           relationships between hubs and standalones."""
        from pyanaconda.ui.gui.spokes import StandaloneSpoke

        # First, grab a list of all the standalone spokes.
        standalones = self._collectActionClasses(self.paths["spokes"], StandaloneSpoke)

        # Second, order them according to their relationship
        return self._orderActionClasses(standalones, hubs)

    def _instantiateAction(self, actionClass):
        # Check if this action is to be shown in the supported environments.
        if self._is_standalone_class(actionClass):
            if not any(actionClass.should_run(environ, self.data) for environ in flags.environs):
                return None

        # Instantiate an action on-demand, passing the arguments defining our
        # spoke API and setting up continue/quit signal handlers.
        obj = actionClass(self.data, self.storage, self.payload)

        # set spoke search paths in Hubs
        if hasattr(obj, "set_path"):
            obj.set_path("spokes", self.paths["spokes"])
            obj.set_path("categories", self.paths["categories"])

        # If we are doing a kickstart install, some standalone spokes
        # could already be filled out.  In that case, we do not want
        # to display them.
        if self._is_standalone(obj):
            if obj.completed:
                del(obj)
                return None
            elif flags.automatedInstall:
                autoinstall_stopped("User interaction required on standalone spoke %s" %
                                    obj.__class__.__name__)

        # Use connect_after so classes can add actions before we change screens
        obj.window.connect_after("continue-clicked", self._on_continue_clicked)
        obj.window.connect_after("quit-clicked", self._on_quit_clicked)

        return obj

    def run(self):
        (success, _args) = Gtk.init_check(None)
        if not success:
            raise RuntimeError("Failed to initialize Gtk")

        # Check if the GUI lock has already been taken
        if self._gui_lock and not self._gui_lock.acquire(False):
            # Gtk main loop running. That means python-meh caught exception
            # and runs its main loop. Do not crash Gtk by running another one
            # from a different thread and just wait until python-meh is
            # finished, then quit.
            unbusyCursor()
            log.error("Unhandled exception caught, waiting for python-meh to "\
                      "exit")

            thread_manager.wait_for_error_threads()
            sys.exit(1)

        try:
            # Apply a widget-scale to hidpi monitors
            self._widgetScale()

            while not self._currentAction:
                self._currentAction = self._instantiateAction(self._actions[0])
                if not self._currentAction:
                    self._actions.pop(0)

                if not self._actions:
                    return

            self._currentAction.initialize()
            self._currentAction.refresh()

            self._currentAction.window.set_beta(not self._isFinal)
            self._currentAction.window.set_property("distribution", self._distributionText())

            # Set some program-wide settings.
            settings = Gtk.Settings.get_default()
            settings.set_property("gtk-font-name", "Cantarell")
            settings.set_property("gtk-icon-theme-name", "Adwaita")

            # Get the path to the application data
            data_path = os.environ.get("ANACONDA_DATA", "/usr/share/anaconda")

            # Apply the application stylesheet
            css_path = os.path.join(data_path, "anaconda-gtk.css")
            provider = Gtk.CssProvider()
            provider.load_from_path(css_path)
            Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

            # Add the application icons to the theme
            icon_path = os.path.join(data_path, "pixmaps")
            icon_theme = Gtk.IconTheme.get_default()
            icon_theme.append_search_path(icon_path)

            # Apply the custom stylesheet
            if conf.ui.custom_stylesheet:
                try:
                    provider = Gtk.CssProvider()
                    provider.load_from_path(conf.ui.custom_stylesheet)
                    Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider,
                            STYLE_PROVIDER_PRIORITY_CUSTOM)
                except GError as e:
                    log.error("Custom stylesheet %s failed to load:\n%s",
                              conf.ui.custom_stylesheet, e)

            # Look for updates to the stylesheet and apply them at a higher priority
            for updates_dir in ("updates", "product"):
                updates_css = "/run/install/%s/anaconda-gtk.css" % updates_dir
                if os.path.exists(updates_css):
                    provider = Gtk.CssProvider()
                    provider.load_from_path(updates_css)
                    Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider,
                            STYLE_PROVIDER_PRIORITY_UPDATES)

            self.mainWindow.setCurrentAction(self._currentAction)
            # the window corresponding to the ection should now be visible to the user
            self._currentAction.entered.emit(self._currentAction)

            # Do this at the last possible minute.
            unbusyCursor()
        # If anything went wrong before we start the Gtk main loop, release
        # the gui lock and re-raise the exception so that meh can take over
        except Exception:
            self._gui_lock.release()
            raise

        Gtk.main()

    ###
    ### MESSAGE HANDLING METHODS
    ###
    @async_action_wait
    def showError(self, message):
        dlg = ErrorDialog(None)

        with self.mainWindow.enlightbox(dlg.window):
            dlg.refresh(message)
            dlg.run()
            dlg.window.destroy()

        # the dialog has the only button -- "Exit installer", so just do so
        util.ipmi_report(constants.IPMI_ABORTED)
        sys.exit(1)

    @async_action_wait
    def showDetailedError(self, message, details, buttons=None):
        from pyanaconda.ui.gui.spokes.lib.detailederror import DetailedErrorDialog
        buttons = buttons or [C_("GUI|Detailed Error Dialog", "_Quit")]
        dlg = DetailedErrorDialog(None, buttons=buttons, label=message)

        with self.mainWindow.enlightbox(dlg.window):
            dlg.refresh(details)
            rc = dlg.run()
            dlg.window.destroy()
            return rc

    @async_action_wait
    def showYesNoQuestion(self, message):
        dlg = Gtk.MessageDialog(flags=Gtk.DialogFlags.MODAL,
                                message_type=Gtk.MessageType.QUESTION,
                                buttons=Gtk.ButtonsType.NONE,
                                message_format=message)
        dlg.set_decorated(False)
        dlg.add_buttons(C_("GUI|Yes No Dialog", "_No"), 0,
                        C_("GUI|Yes No Dialog", "_Yes"), 1)
        dlg.set_default_response(1)

        with self.mainWindow.enlightbox(dlg):
            rc = dlg.run()
            dlg.destroy()

        return bool(rc)

    ###
    ### SIGNAL HANDLING METHODS
    ###
    def _on_continue_clicked(self, window, user_data=None):
        if not window.get_may_continue() or window != self._currentAction.window:
            return

        # The continue button may still be clickable between this handler finishing
        # and the next window being displayed, so turn the button off.
        window.set_may_continue(False)

        # If we're on the last screen, clicking Continue quits.
        if len(self._actions) == 1:
            Gtk.main_quit()
            return

        nextAction = None
        ndx = 0

        # If the current action wants us to jump to an arbitrary point ahead,
        # look for where that is now.
        if self._currentAction.skipTo:
            found = False
            for ndx in range(1, len(self._actions)):
                if self._actions[ndx].__class__.__name__ == self._currentAction.skipTo:
                    found = True
                    break

            # If we found the point in question, compose a new actions list
            # consisting of the current action, the one to jump to, and all
            # the ones after.  That means the rest of the code below doesn't
            # have to change.
            if found:
                self._actions = [self._actions[0]] + self._actions[ndx:]

        # _instantiateAction returns None for actions that should not be
        # displayed (because they're already completed, for instance) so skip
        # them here.
        while not nextAction:
            nextAction = self._instantiateAction(self._actions[1])
            if not nextAction:
                self._actions.pop(1)

            if not self._actions:
                sys.exit(0)

        nextAction.initialize()
        nextAction.window.set_beta(self._currentAction.window.get_beta())
        nextAction.window.set_property("distribution", self._distributionText())

        if not nextAction.showable:
            self._currentAction.window.hide()
            self._actions.pop(0)
            self._on_continue_clicked(nextAction)
            return

        self._currentAction.exited.emit(self._currentAction)

        nextAction.refresh()

        # Do this last.  Setting up curAction could take a while, and we want
        # to leave something on the screen while we work.
        self.mainWindow.setCurrentAction(nextAction)
        # the new spoke should be now visible, trigger the entered signal
        nextAction.entered.emit(nextAction)
        self._currentAction = nextAction
        self._actions.pop(0)

    def _on_quit_clicked(self, win, _userData=None):

        if not win.get_quit_button():
            return

        dialog = self._quitDialog(None)
        with self.mainWindow.enlightbox(dialog.window):
            rc = dialog.run()
            dialog.window.destroy()

        if rc == 1:
            self._currentAction.exited.emit(self._currentAction)
            util.ipmi_abort()
            Gtk.main_quit()


class GraphicalExceptionHandlingIface(meh.ui.gui.GraphicalIntf):
    """
    Class inheriting from python-meh's GraphicalIntf and overriding methods
    that need some modification in Anaconda.

    """

    def __init__(self, lightbox_func):
        """
        :param lightbox_func: a function that creates lightbox for a given
                              window
        :type lightbox_func: None -> None

        """
        super().__init__()

        self._lightbox_func = lightbox_func

    def mainExceptionWindow(self, text, exnFile, *args, **kwargs):
        meh_intf = meh.ui.gui.GraphicalIntf()
        exc_window = meh_intf.mainExceptionWindow(text, exnFile)
        exc_window.main_window.set_decorated(False)

        self._lightbox_func()

        ANACONDA_WINDOW_GROUP.add_window(exc_window.main_window)

        # the busy cursor may be set
        unbusyCursor()

        return exc_window
