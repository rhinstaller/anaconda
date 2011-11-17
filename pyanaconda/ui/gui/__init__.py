# Base classes for the graphical user interface.
#
# Copyright (C) 2011  Red Hat, Inc.
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
import importlib, inspect, os

from pyanaconda.ui import UserInterface

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

class GraphicalUserInterface(UserInterface):
    """This is the standard GTK+ interface we try to steer everything to using.
       It is suitable for use both directly and via VNC.
    """
    def __init__(self):
        UserInterface.__init__(self)

        self._hubs = []
        self._ui = None

        # This is a hack to make sure the AnacondaWidgets library gets loaded
        # before the introspection stuff.
        import ctypes
        ctypes.CDLL("libAnacondaWidgets.so.0", ctypes.RTLD_GLOBAL)

    def setup(self, data):
        from hubs.summary import SummaryHub
        from spokes import StandaloneSpoke

        from pyanaconda.product import isFinal, productName, productVersion

        self._hubs.append(SummaryHub)

        # First, grab a list of all the standalone spokes.
        standalones = collect("spokes", lambda obj: issubclass(obj, StandaloneSpoke) and \
                                                    getattr(obj, "preForHub", False) or getattr(obj, "postForHub", False))

        actionClasses = []
        for hub in self._hubs:
            actionClasses.extend(sorted(filter(lambda obj: getattr(obj, "preForHub", None) == hub, standalones),
                                        key=lambda obj: obj.priority))
            actionClasses.append(hub)
            actionClasses.extend(sorted(filter(lambda obj: getattr(obj, "postForHub", None) == hub, standalones),
                                        key=lambda obj: obj.priority))

        # Instantiate all hubs and their pre/post standalone spokes, passing
        # the arguments defining our spoke API and setting up continue/quit
        # signal handlers.
        self._actions = []
        for klass in actionClasses:
            obj = klass(data)
            obj.populate()

            if not obj.showable:
                continue

            obj.register_event_cb("continue", self._on_continue_clicked)
            obj.register_event_cb("quit", self._on_quit_clicked)

            self._actions.append(obj)

        # If we set these values on the very first window shown, they will get
        # propagated to later ones.
        self._actions[0].setup()

        self._actions[0].window.set_beta(not isFinal)
        self._actions[0].window.set_property("distribution", _("%s %s INSTALLATION") % (productName, productVersion))

    def run(self):
        from gi.repository import Gtk

        self._actions[0].window.show_all()
        Gtk.main()

    def _on_continue_clicked(self):
        # If we're on the last screen, clicking Continue is the same as clicking Quit.
        if len(self._actions) == 1:
            self._on_quit_clicked()
            return

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

        self._actions[1].setup()
        self._actions[1].window.set_beta(self._actions[0].window.get_beta())
        self._actions[1].window.set_property("distribution", self._actions[0].window.get_property("distribution"))

        # Do this last.  Setting up curAction could take a while, and we want
        # to leave something on the screen while we work.
        self._actions[1].window.show_all()
        self._actions[0].window.hide()
        self._actions.pop(0)

    def _on_quit_clicked(self):
        from gi.repository import Gtk
        Gtk.main_quit()

class UIObject(object):
    """This is the base class from which all other UI classes are derived.  It
       thus contains only attributes and methods that are common to everything
       else.  It should not be directly instantiated.

       Class attributes:

       builderObjects   -- A list of UI object name that should be extracted from
                           uiFile and exposed for this class to use.  If this
                           list is empty, all objects will be exposed.
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

           data         -- An instance of a pykickstart Handler object.  The
                           Hub never directly uses this instance.  Instead, it
                           passes it down into Spokes when they are created
                           and applied.  The Hub simply stores this instance
                           so it doesn't need to be passed by the user.
        """
        if self.__class__ is UIObject:
            raise TypeError("UIObject is an abstract class")

        self.data = data

        from gi.repository import Gtk

        self.builder = Gtk.Builder()
        self._window = None

        if self.builderObjects:
            self.builder.add_objects_from_file(self._findUIFile(), self.builderObjects)
        else:
            self.builder.add_from_file(self._findUIFile())

        self.builder.connect_signals(self)

    def _findUIFile(self):
        testPath = os.path.normpath(os.path.dirname(__file__) + "/" + self.uiFile)
        if os.path.isfile(testPath) and os.access(testPath, os.R_OK):
            return testPath

        raise IOError("Could not load UI file '%s' for object '%s'" % (self.uiFile, self))

    def populate(self):
        """Perform whatever actions are necessary to pre-fill the UI with
           values.  This method is called only once, when the object is created,
           and as such is the place where stores should be filled in.  This is
           like a one-time setup() method.
        """
        pass

    def setup(self):
        """Perform whatever actions are necessary to set defaults on the UI.
           This method may be called multiple times, so it's important to not
           do things like populate stores, as it may result in the store having
           duplicates.
        """
        pass

    def showable(self):
        """Should this object even be shown?  This method is useful for checking
           some precondition before this screen is shown.  If False is returned,
           the screen will be skipped though it will still have been
           instantiated.
        """
        return True

    @property
    def skipTo(self):
        """If this property returns something other than None, it must be the
           name of a class.  Then, the interface will skip to the first
           instance of that class in the action list instead of going on to
           whatever the next action is normally.

           Note that actions may only skip ahead, never backwards.  Also,
           standalone spokes may not skip to an individual spoke off a hub.
           They can only skip to the hub itself.
        """
        return None

    def teardown(self):
        """Perform whatever actions are necessary to clean up after this object
           is done.  It's not necessary for every subclass to have an instance
           of this method.

           NOTE:  It is important for this method to not destroy self.window if
           you are making a Spoke or Hub subclass.  It is assumed that once
           these are instantiated, they live until the program terminates.  This
           is required for various status notifications.
        """
        pass

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

def collect(subpath, pred):
    """Traverse the subdirectory (given by subpath) of this module's current
       directory and find all classes that math the given category.  This is
       then returned as a list of classes.  If category is None, this method
       will return a list of all matching subclasses.

       It is suggested you use collect_categories or collect_spokes instead of
       this lower-level method.
    """
    retval = []
    for module_file in os.listdir(os.path.dirname(__file__) + "/" + subpath):
        if not module_file.endswith(".py") or module_file in [__file__, "__init__.py"]:
            continue

        mod_name = module_file[:-3]
        module = importlib.import_module("pyanaconda.ui.gui.%s.%s" % (subpath, mod_name))

        p = lambda obj: inspect.isclass(obj) and pred(obj)

        for (name, val) in inspect.getmembers(module, p):
            retval.append(val)

    return retval
