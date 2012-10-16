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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Chris Lumens <clumens@redhat.com>
#
import importlib, inspect, os, sys, time
import meh.ui.gui

from gi.repository import Gdk

from pyanaconda.ui import UserInterface, common
from pyanaconda.ui.gui.utils import enlightbox, gtk_thread_wait

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("anaconda")

__all__ = ["GraphicalUserInterface", "UIObject", "busyCursor", "unbusyCursor"]

_screenshotIndex = 0

class GraphicalUserInterface(UserInterface):
    """This is the standard GTK+ interface we try to steer everything to using.
       It is suitable for use both directly and via VNC.
    """
    def __init__(self, storage, payload, instclass):
        UserInterface.__init__(self, storage, payload, instclass)

        self._actions = []
        self._hubs = []
        self._ui = None

        # This is a hack to make sure the AnacondaWidgets library gets loaded
        # before the introspection stuff.
        import ctypes
        ctypes.CDLL("libAnacondaWidgets.so.0", ctypes.RTLD_GLOBAL)

    def setup(self, data):
        from hubs.summary import SummaryHub
        from hubs.progress import ProgressHub
        from spokes import StandaloneSpoke

        busyCursor()

        self._hubs.extend([SummaryHub, ProgressHub])

        # First, grab a list of all the standalone spokes.
        path = os.path.join(os.path.dirname(__file__), "spokes")
        actionClasses = self.getActionClasses("pyanaconda.ui.gui.spokes.%s", path, self._hubs, StandaloneSpoke)

        # Instantiate all hubs and their pre/post standalone spokes, passing
        # the arguments defining our spoke API and setting up continue/quit
        # signal handlers.
        for klass in actionClasses:
            obj = klass(data, self.storage, self.payload, self.instclass)

            # If we are doing a kickstart install, some standalone spokes
            # could already be filled out.  In taht case, we do not want
            # to display them.
            if isinstance(obj, StandaloneSpoke) and obj.completed:
                del(obj)
                continue

            obj.register_event_cb("continue", self._on_continue_clicked)
            obj.register_event_cb("quit", self._on_quit_clicked)

            self._actions.append(obj)

    def run(self):
        from gi.repository import Gtk

        unbusyCursor()

        if Gtk.main_level() > 0:
            # Gtk main loop running. That means python-meh caught exception
            # and runs its main loop. Do not crash Gtk by running another one
            # from a different thread and just wait until python-meh is
            # finished, then quit.
            log.error("Unhandled exception caught, waiting for python-meh to "\
                      "exit")
            while Gtk.main_level() > 0:
                time.sleep(2)

            sys.exit(0)

        from pyanaconda.product import isFinal, productName, productVersion

        # If we set these values on the very first window shown, they will get
        # propagated to later ones.
        self._actions[0].initialize()
        self._actions[0].refresh()

        self._actions[0].window.set_beta(not isFinal)
        self._actions[0].window.set_property("distribution", _("%(productName)s %(productVersion)s INSTALLATION") % \
                                             {"productName": productName.upper(), "productVersion": productVersion})

        self._actions[0].window.show_all()
        Gtk.main()

    ###
    ### MESSAGE HANDLING METHODS
    ###
    @gtk_thread_wait
    def showError(self, message):
        from gi.repository import AnacondaWidgets, Gtk
        dlg = Gtk.MessageDialog(flags=Gtk.DialogFlags.MODAL,
                                message_type=Gtk.MessageType.ERROR,
                                buttons=Gtk.ButtonsType.NONE,
                                message_format=message)
        dlg.add_button(_("_Exit Installer"), 0)
        
        with enlightbox(self._actions[0].window, dlg):
            dlg.run()
            dlg.destroy()

    @gtk_thread_wait
    def showYesNoQuestion(self, message):
        from gi.repository import AnacondaWidgets, Gtk
        dlg = Gtk.MessageDialog(flags=Gtk.DialogFlags.MODAL,
                                message_type=Gtk.MessageType.QUESTION,
                                buttons=Gtk.ButtonsType.NONE,
                                message_format=message)
        dlg.add_buttons(_("_No"), 0, _("_Yes"), 1)
        dlg.set_default_response(1)

        with enlightbox(self._actions[0].window, dlg):
            rc = dlg.run()
            dlg.destroy()

        return bool(rc)


    def mainExceptionWindow(self, text, exn_file, *args, **kwargs):
        from gi.repository import Gtk, AnacondaWidgets

        meh_intf = meh.ui.gui.GraphicalIntf()
        exc_window = meh_intf.mainExceptionWindow(text, exn_file)

        # exception may appear before self._actions gets populated
        if len(self._actions) > 0:
            lightbox = AnacondaWidgets.lb_show_over(self._actions[0].window)
            exc_window.main_window.set_transient_for(lightbox)

        # without WindowGroup, python-meh's window is insensitive if it appears
        # above a spoke (Gtk.Window running its own Gtk.main loop)
        window_group = Gtk.WindowGroup()
        window_group.add_window(exc_window.main_window)

        return exc_window

    def saveExceptionWindow(self, account_manager, signature, *args, **kwargs):
        meh_intf = meh.ui.gui.GraphicalIntf()
        meh_intf.saveExceptionWindow(account_manager, signature)

    ###
    ### SIGNAL HANDLING METHODS
    ###
    def _on_continue_clicked(self):
        # If we're on the last screen, clicking Continue quits.
        if len(self._actions) == 1:
            sys.exit(0)
            return

        ndx = 0

        # If the current action wants us to jump to an arbitrary point ahead,
        # look for where that is now.
        if self._actions[0].skipTo:
            found = False
            for ndx in range(1, len(self._actions)):
                if self._actions[ndx].__class__.__name__ == self._actions[0].skipTo:
                    found = True
                    break

            # If we found the point in question, compose a new actions list
            # consisting of the current action, the one to jump to, and all
            # the ones after.  That means the rest of the code below doesn't
            # have to change.
            if found:
                self._actions = [self._actions[0]] + self._actions[ndx:]

        self._actions[1].initialize()
        self._actions[1].window.set_beta(self._actions[0].window.get_beta())
        self._actions[1].window.set_property("distribution", self._actions[0].window.get_property("distribution"))

        if not self._actions[1].showable:
            self._actions[0].window.hide()
            self._actions.pop(0)
            self._on_continue_clicked()
            return

        self._actions[1].refresh()

        # Do this last.  Setting up curAction could take a while, and we want
        # to leave something on the screen while we work.
        self._actions[1].window.show_all()
        self._actions[0].window.hide()
        self._actions.pop(0)

    def _on_quit_clicked(self):
        dialog = QuitDialog(None)
        with enlightbox(self._actions[0].window, dialog.window):
            rc = dialog.run()
            dialog.window.destroy()

        if rc == 1:
            sys.exit(0)

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
       uiFile           -- The location of an XML file that describes the layout
                           of widgets shown by this object.  UI files are
                           searched for relative to the same directory as this
                           object's module.
    """
    builderObjects = []
    mainWidgetName = None
    uiFile = ""

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
        common.UIObject.__init__(self, data)

        if self.__class__ is GUIObject:
            raise TypeError("GUIObject is an abstract class")

        # This couldn't possibly be a bigger hack job.  This structure holds the
        # untranslated strings out of each widget.  retranslate works by taking the
        # string out of a widget, translating it, and then cramming it back into
        # the widget.  When we go to change language a second time, the fetched
        # string will be the translated one.  Strings in gettext are keyed on the
        # original English, so we'd be looking up translations by translations.
        self._origStrings = {}

        self.skipTo = None
        self.applyOnSkip = False

        from gi.repository import Gtk

        self.builder = Gtk.Builder()
        self._window = None

        if self.builderObjects:
            self.builder.add_objects_from_file(self._findUIFile(), self.builderObjects)
        else:
            self.builder.add_from_file(self._findUIFile())

        self.builder.connect_signals(self)
        self.window.connect("key-release-event", self._handlePrntScreen)

    def _findUIFile(self):
        path = os.environ.get("UIPATH", "./:/tmp/updates/:/tmp/updates/ui/:/usr/share/anaconda/ui/")
        for d in path.split(":"):
            testPath = os.path.normpath(d + self.uiFile)
            if os.path.isfile(testPath) and os.access(testPath, os.R_OK):
                return testPath

        raise IOError("Could not load UI file '%s' for object '%s'" % (self.uiFile, self))

    def _handlePrntScreen(self, window, event):
        from gi.repository import Gdk

        global _screenshotIndex

        if event.keyval != Gdk.KEY_Print:
            return

        # Make sure the screenshot directory exists.
        if not os.access("/tmp/anaconda-screenshots", os.W_OK):
            os.mkdir("/tmp/anaconda-screenshots")

        fn = "/tmp/anaconda-screenshots/screenshot-%04d.png" % _screenshotIndex

        win = window.get_window()
        width = win.get_width()
        height = win.get_height()

        pixbuf = Gdk.pixbuf_get_from_window(win, 0, 0, width, height)
        pixbuf.savev(fn, "png", [], [])

        _screenshotIndex += 1

    def retranslate(self):
        """This method should be called when the current language is changed
           in order to update the UI for the new language.  Since we don't get
           any toolkit help for this, it is largely a manual process.
        """
        from gi.repository import AnacondaWidgets, Gtk

        # NOTE:  If you see widgets on a screen that remain untranslated even
        # when you know there are translations, the widgets likely need to be
        # added to this dict.
        # Widget class -> (getter, setter)   -or-
        # Widget class -> (setter, )
        widgetMap = { AnacondaWidgets.StandaloneWindow: ("retranslate", ),
                      Gtk.Button: ("get_label", "set_label"),
                      Gtk.Label: ("get_label", "set_label") }
        classes = widgetMap.keys()

        objs = filter(lambda obj: obj.__class__ in classes, self.builder.get_objects())
        for obj in objs:
            klass = obj.__class__
            funcs = widgetMap[klass]

            if len(funcs) == 1:
                getattr(obj, funcs[0])()
            else:
                # Only store the string once, so we make sure to get the original.
                if not obj in self._origStrings:
                    self._origStrings[obj] = getattr(obj, funcs[0])()

                before = self._origStrings[obj]
                xlated = _(before)
                getattr(obj, funcs[1])(xlated)

    @property
    def window(self):
        """Return the top-level object out of the GtkBuilder representation
           previously loaded by the load method.
        """

        # This will raise an AttributeError if the subclass failed to set a
        # mainWidgetName attribute, which is exactly what I want.
        if not self._window:
            self._window = self.builder.get_object(self.mainWidgetName)

        return self._window

class QuitDialog(GUIObject):
    builderObjects = ["quitDialog"]
    mainWidgetName = "quitDialog"
    uiFile = "main.glade"

    def run(self):
        rc = self.window.run()
        return rc

def busyCursor():
    window = Gdk.get_default_root_window()
    window.set_cursor(Gdk.Cursor(Gdk.CursorType.WATCH))

def unbusyCursor():
    window = Gdk.get_default_root_window()
    window.set_cursor(Gdk.Cursor(Gdk.CursorType.ARROW))
