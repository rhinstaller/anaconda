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
import inspect, os, sys, time, site
import meh.ui.gui

from gi.repository import Gdk, Gtk, AnacondaWidgets

from pyanaconda.i18n import _
from pyanaconda import product

from pyanaconda.ui import UserInterface, common
from pyanaconda.ui.gui.utils import enlightbox, gtk_action_wait
import os.path

import logging
log = logging.getLogger("anaconda")

__all__ = ["GraphicalUserInterface", "busyCursor", "unbusyCursor", "QuitDialog"]

_screenshotIndex = 0

ANACONDA_WINDOW_GROUP = Gtk.WindowGroup()

class GUICheck(object):
    """Handle an input validation check."""

    # Use as a return value to indicate a passed check
    CHECK_OK = None

    def __init__(self, parent, editable, run_check, check_data, set_error):
        """Create a new input validation check.

           :param parent: The parent GUIObject. When a check state changes,
                          the GUICheck will call set_error(check, check-state)
           :type parent:  GUIObject
           
           :param editable: The input field being checked
           :type editable:  GtkEditable

           :param run_check: The check function. The function is called as
                             check(editable, check_data). The return value is an
                             error state object or CHECK_OK if the check succeeds.
           :type run_check:  function

           :param check_data: An optional parameter passed to check().

           :param set_error: A function called when the state of this check
                             changes. The parameters are (GUICheck, run_check_return).
                             The return value is ignored.
           :type set_error:  function
        """

        self._parent = parent
        self._editable = editable
        self._run_check = run_check
        self._check_data = check_data
        self._set_error = set_error

        # Set to the Gtk handler ID in enable()
        self._handler_id = None

        # Initial check state
        self._check_status = None

        self.enable()

    def enable(self):
        """Enable the check.

           enable() does not check the current state of the input field. To
           check the current state, run update_check_status() after enable().
        """
        if not self._handler_id:
            self._handler_id = self._editable.connect_after("changed", self.update_check_status)

    def disable(self):
        """Disable the check. The check will no longer appear in failed_checks,
           but disabling the check does not call set_error to update the
           GUIObject's state.
        """
        if self._handler_id:
            self._editable.disconnect(self._handler_id)
            self._handler_id = None
            self._check_status = None

    def update_check_status(self, editable=None, check_data=None):
        """Run an input validation check."""

        # Allow check parameters to be overriden in parameters
        if editable is None:
            editable = self._editable
        if check_data is None:
            check_data = self._check_data

        new_check_status = self._run_check(editable, check_data)
        check_status_changed = (self._check_status != new_check_status)
        self._check_status = new_check_status

        if check_status_changed:
            self._set_error(self, self._check_status)

    @property
    def check_status(self):
        return self._check_status

    @property
    def editable(self):
        return self._editable

    @property
    def check_data(self):
        return self._check_data
        
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

    screenshots_directory = "/tmp/anaconda-screenshots"

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

        self.skipTo = None
        self.applyOnSkip = False

        self.builder = Gtk.Builder()
        self.builder.set_translation_domain("anaconda")
        self._window = None

        if self.builderObjects:
            self.builder.add_objects_from_file(self._findUIFile(), self.builderObjects)
        else:
            self.builder.add_from_file(self._findUIFile())

        ANACONDA_WINDOW_GROUP.add_window(self.window)
        self.builder.connect_signals(self)
        self.window.connect("key-release-event", self._handlePrntScreen)

        self._check_list = []

    def _findUIFile(self):
        path = os.environ.get("UIPATH", "./:/tmp/updates/:/tmp/updates/ui/:/usr/share/anaconda/ui/")
        dirs = path.split(":")

        # append the directory where this UIObject is defined
        dirs.append(os.path.dirname(inspect.getfile(self.__class__)))

        for d in dirs:
            testPath = os.path.join(d, self.uiFile)
            if os.path.isfile(testPath) and os.access(testPath, os.R_OK):
                return testPath

        raise IOError("Could not load UI file '%s' for object '%s'" % (self.uiFile, self))

    def _handlePrntScreen(self, window, event):
        global _screenshotIndex

        if event.keyval != Gdk.KEY_Print:
            return

        # Make sure the screenshot directory exists.
        if not os.access(self.screenshots_directory, os.W_OK):
            os.mkdir(self.screenshots_directory)

        fn = os.path.join(self.screenshots_directory,
                          "screenshot-%04d.png" % _screenshotIndex)

        win = window.get_window()
        width = win.get_width()
        height = win.get_height()

        pixbuf = Gdk.pixbuf_get_from_window(win, 0, 0, width, height)
        pixbuf.savev(fn, "png", [], [])

        _screenshotIndex += 1

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

    def add_check(self, editable, run_check, check_data=None, set_error=None):
        """Add an input validation check to this object.

           This function creates new GUICheck object and adds it to this
           GUIObject. The check is run any time the input field changes.
           If the result of a check changes, the check object will call
           the set_error function. By default, set_error will call
           self.set_warning with the status of the first failed check.

           :param editable: the input field to validate
           :type editable: GtkEditable

           :param run_check: a function called to validate the input field. The
                         parameters are (editable, check_data). The return
                         value is an object used by update_check, or
                         GUICheck.CHECK_OK if the check passes.
           :type run_check: function
           
           :param check_data: additional data to pass to the check function

           :param set_error: a function called when a check changes state. The
                         parameters are (GUICheck, run_check_return).  The
                         return value is ignored.
           :type set_error: function
           
           :returns: A check object
           :rtype: GUICheck
        """

        if not set_error:
            set_error = self.set_check_error

        checkRef = GUICheck(self, editable, run_check, check_data, set_error)
        self._check_list.append(checkRef)
        return checkRef

    def add_re_check(self, editable, regex, message, set_error=None):
        """Add a check using a regular expresion.
           
           :param editable: the input field to validate
           :type editable:  GtkEditable

           :param regex: the regular expression to use to check the input
           :type regex:  re.RegexObject

           :param message: The message to set if the regex does not match
           :type message:  str

           :param set_error: a function called when a check changes state. The
                         parameters are (GUICheck, run_check_return).  The
                         return value is ignored.
           :type set_error: function

           :returns: A check object
           :rtype: GUICheck
        """
        if not set_error:
            set_error = self.set_check_error
        return self.add_check(editable=editable, run_check=check_re, 
                check_data={'regex': regex, 'message': message}, set_error=set_error)

    def update_check(self, check, check_status):
        """This method is called when the state of a check in the check list changes.

           :param check: The check object that changed
           :type check:  GUICheck

           :param check_status: The new status of the check
        """
        raise NotImplementedError()

    def set_check_error(self, check, check_return):
        """Update the warning with the input validation check error."""
        # Grab the first failed check
        failed_check = next(self.failed_checks, None)

        self.clear_info()
        if failed_check:
            self.set_warning(failed_check.check_status)
            self.window.show_all()

    @property
    def failed_checks(self):
        """A generator of all failed input checks"""
        return (c for c in self._check_list if c.check_status)

    @property
    def checks(self):
        """An iterator over all input checks"""
        return self._check_list.__iter__()

class GUIDialog(GUIObject):
    """This is an abstract for creating dialog windows. It implements the
       update_check interface to display an error message when an input
       validation fails.

       GUIDialog does not define where errors are displayed, so classes
       that derive from GUIDialog must define error labels and include them
       as the check_data parameter to add_check. More than one check can use
       the same label: the message from the first failed check will update the
       label.
    """

    def __init__(self, data):
        if self.__class__ is GUIDialog:
            raise TypeError("GUIDialog is an abstract class")

        GUIObject.__init__(self, data)

    def add_check_with_error_label(self, editable, error_label, run_check, 
            check_data=None, set_error=None):
        """Add an input validation check to this dialog. The error_label will
           be added to the check_data for the validation check and will be
           used to display the error message if the check fails.

           :param editable: the input field to validate
           :type editable: GtkEditable

           :param error_label: the label in which to display the error data
           :type error_label:  GtkLabel

           :param run_check: a function called to validate the input field. The
                         parameters are (editable, check_data). The return
                         value is an object used by update_check, or
                         GUICheck.CHECK_OK if the check passes.
           :type run_check: function
           
           :param check_data: additional data to pass to the check function

           :param set_error: a function called when a check changes state. The
                         parameters are (GUICheck, run_check_return).  The
                         return value is ignored.
           :type set_error: function
           
           :returns: A check object
           :rtype: GUICheck
        """
        if not set_error:
            set_error = self.set_check_error

        return self.add_check(editable=editable, run_check=run_check, 
                check_data={'error_label': error_label, 'message': check_data},
                set_error=set_error)

    def add_re_check_with_error_label(self, editable, error_label, regex, message, set_error=None):
        """Add a check using a regular expression."""
        # Use the GUIObject function so we can create the check_data dictionary here
        if not set_error:
            set_error = self.set_check_error

        return self.add_check(editable=editable, run_check=check_re,
                check_data={'error_label': error_label, 'message': message, 'regex': regex},
                set_error=set_error)

    def set_check_error(self, check, check_return):
        """Update all input check failure messages.

           If multiple checks use the same GtkLabel, only the first one will
           be used.
        """

        # If the signaling check passed, clear its error label
        if not check_return:
            if 'error_label' in check.check_data:
                check.check_data['error_label'].set_text('')

        # Keep track of which labels have errors set. If we see an error for
        # a label that's already been set, skip it.
        labels_seen = []
        for failed_check in self.failed_checks:
            if not 'error_label' in failed_check.check_data:
                continue

            label = failed_check.check_data['error_label']
            if label not in labels_seen:
                labels_seen.append(label)
                label.set_text(failed_check.check_status)

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

class GraphicalUserInterface(UserInterface):
    """This is the standard GTK+ interface we try to steer everything to using.
       It is suitable for use both directly and via VNC.
    """
    def __init__(self, storage, payload, instclass,
                 distributionText = product.distributionText, isFinal = product.isFinal,
                 quitDialog = QuitDialog):

        UserInterface.__init__(self, storage, payload, instclass)

        self._actions = []
        self._currentAction = None
        self._ui = None

        self.data = None

        self._distributionText = distributionText
        self._isFinal = isFinal
        self._quitDialog = quitDialog
        self._mehInterface = GraphicalExceptionHandlingIface(
                                    self.lightbox_over_current_action)

    basemask = "pyanaconda.ui.gui"
    basepath = os.path.dirname(__file__)
    updatepath = "/tmp/updates/pyanaconda/ui/gui"
    sitepackages = [os.path.join(dir, "pyanaconda", "ui", "gui")
                    for dir in site.getsitepackages()]
    pathlist = set([updatepath, basepath] + sitepackages)

    paths = UserInterface.paths + {
            "categories": [(basemask + ".categories.%s",
                        os.path.join(path, "categories"))
                        for path in pathlist],
            "spokes": [(basemask + ".spokes.%s",
                        os.path.join(path, "spokes"))
                        for path in pathlist],
            "hubs": [(basemask + ".hubs.%s",
                      os.path.join(path, "hubs"))
                      for path in pathlist]
            }

    @property
    def tty_num(self):
        return 7

    @property
    def meh_interface(self):
        return self._mehInterface

    def _list_hubs(self):
        """Return a list of Hub classes to be imported to this interface"""
        from pyanaconda.ui.gui.hubs.summary import SummaryHub
        from pyanaconda.ui.gui.hubs.progress import ProgressHub
        return [SummaryHub, ProgressHub]

    def _is_standalone(self, obj):
        """Is the spoke passed as obj standalone?"""
        from pyanaconda.ui.gui.spokes import StandaloneSpoke
        return isinstance(obj, StandaloneSpoke)

    def setup(self, data):
        busyCursor()

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

    def lightbox_over_current_action(self, window):
        """
        Creates lightbox over current action for the given window. Or
        DOES NOTHING IF THERE ARE NO ACTIONS.

        """

        # if there are no actions (not populated yet), we can do nothing
        if len(self._actions) > 0 and self._currentAction:
            lightbox = AnacondaWidgets.Lightbox(parent_window=self._currentAction.window)
            ANACONDA_WINDOW_GROUP.add_window(lightbox)
            window.main_window.set_transient_for(lightbox)

    def _instantiateAction(self, actionClass):
        from pyanaconda.ui.gui.spokes import StandaloneSpoke

        # Instantiate an action on-demand, passing the arguments defining our
        # spoke API and setting up continue/quit signal handlers.
        obj = actionClass(self.data, self.storage, self.payload, self.instclass)

        # set spoke search paths in Hubs
        if hasattr(obj, "set_path"):
            obj.set_path("spokes", self.paths["spokes"])
            obj.set_path("categories", self.paths["categories"])

        # If we are doing a kickstart install, some standalone spokes
        # could already be filled out.  In that case, we do not want
        # to display them.
        if self._is_standalone(obj) and obj.completed:
            del(obj)
            return None

        obj.register_event_cb("continue", self._on_continue_clicked)
        obj.register_event_cb("quit", self._on_quit_clicked)

        return obj

    def run(self):
        (success, args) = Gtk.init_check(None)
        if not success:
            raise RuntimeError("Failed to initialize Gtk")

        if Gtk.main_level() > 0:
            # Gtk main loop running. That means python-meh caught exception
            # and runs its main loop. Do not crash Gtk by running another one
            # from a different thread and just wait until python-meh is
            # finished, then quit.
            unbusyCursor()
            log.error("Unhandled exception caught, waiting for python-meh to "\
                      "exit")
            while Gtk.main_level() > 0:
                time.sleep(2)

            sys.exit(0)

        while not self._currentAction:
            self._currentAction = self._instantiateAction(self._actions[0])
            if not self._currentAction:
                self._actions.pop(0)

            if not self._actions:
                return

        self._currentAction.initialize()
        self._currentAction.refresh()

        self._currentAction.window.set_beta(not self._isFinal)
        self._currentAction.window.set_property("distribution", self._distributionText().upper())

        # Set some program-wide settings.
        settings = Gtk.Settings.get_default()
        settings.set_property("gtk-font-name", "Cantarell")
        settings.set_property("gtk-icon-theme-name", "gnome")

        # Apply the application stylesheet
        provider = Gtk.CssProvider()
        provider.load_from_path("/usr/share/anaconda/anaconda-gtk.css")
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self._currentAction.window.show_all()

        # Do this at the last possible minute.
        unbusyCursor()

        Gtk.main()

    ###
    ### MESSAGE HANDLING METHODS
    ###
    @gtk_action_wait
    def showError(self, message):
        dlg = Gtk.MessageDialog(flags=Gtk.DialogFlags.MODAL,
                                message_type=Gtk.MessageType.ERROR,
                                buttons=Gtk.ButtonsType.NONE,
                                message_format=message)
        dlg.set_decorated(False)
        dlg.add_button(_("_Exit Installer"), 0)

        with enlightbox(self._currentAction.window, dlg):
            dlg.run()
            dlg.destroy()

    @gtk_action_wait
    def showDetailedError(self, message, details):
        from pyanaconda.ui.gui.spokes.lib.detailederror import DetailedErrorDialog
        dlg = DetailedErrorDialog(None, buttons=[_("_Quit")],
                                  label=message)

        with enlightbox(self._currentAction.window, dlg.window):
            dlg.refresh(details)
            rc = dlg.run()
            dlg.window.destroy()

    @gtk_action_wait
    def showYesNoQuestion(self, message):
        dlg = Gtk.MessageDialog(flags=Gtk.DialogFlags.MODAL,
                                message_type=Gtk.MessageType.QUESTION,
                                buttons=Gtk.ButtonsType.NONE,
                                message_format=message)
        dlg.set_decorated(False)
        dlg.add_buttons(_("_No"), 0, _("_Yes"), 1)
        dlg.set_default_response(1)

        with enlightbox(self._currentAction.window, dlg):
            rc = dlg.run()
            dlg.destroy()

        return bool(rc)

    ###
    ### SIGNAL HANDLING METHODS
    ###
    def _on_continue_clicked(self):
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
                return

        nextAction.initialize()
        nextAction.window.set_beta(self._currentAction.window.get_beta())
        nextAction.window.set_property("distribution", self._distributionText().upper())

        if not nextAction.showable:
            self._currentAction.window.hide()
            self._actions.pop(0)
            self._on_continue_clicked()
            return

        nextAction.refresh()

        # Do this last.  Setting up curAction could take a while, and we want
        # to leave something on the screen while we work.
        nextAction.window.show_all()
        self._currentAction.window.hide()
        self._currentAction = nextAction
        self._actions.pop(0)

    def _on_quit_clicked(self):
        dialog = self._quitDialog(None)
        with enlightbox(self._currentAction.window, dialog.window):
            rc = dialog.run()
            dialog.window.destroy()

        if rc == 1:
            sys.exit(0)

class GraphicalExceptionHandlingIface(meh.ui.gui.GraphicalIntf):
    """
    Class inheriting from python-meh's GraphicalIntf and overriding methods
    that need some modification in Anaconda.

    """

    def __init__(self, lightbox_func):
        """
        :param lightbox_func: a function that creates lightbox for a given
                              window
        :type lightbox_func: GtkWindow -> None

        """
        meh.ui.gui.GraphicalIntf.__init__(self)

        self._lightbox_func = lightbox_func

    def mainExceptionWindow(self, text, exn_file, *args, **kwargs):
        meh_intf = meh.ui.gui.GraphicalIntf()
        exc_window = meh_intf.mainExceptionWindow(text, exn_file)
        exc_window.main_window.set_decorated(False)

        self._lightbox_func(exc_window)

        # without a new GtkWindowGroup, python-meh's window is insensitive if it
        # appears above a spoke (Gtk.Window running its own Gtk.main loop)
        window_group = Gtk.WindowGroup()
        window_group.add_window(exc_window.main_window)

        # the busy cursor may be set
        unbusyCursor()

        return exc_window

def busyCursor():
    window = Gdk.get_default_root_window()
    window.set_cursor(Gdk.Cursor(Gdk.CursorType.WATCH))

def unbusyCursor():
    window = Gdk.get_default_root_window()
    window.set_cursor(Gdk.Cursor(Gdk.CursorType.ARROW))

def check_re(editable, data):
    """Perform an input validation check against a regular expression.

       :param editable: The input field being checked
       :type editable:  GtkEditable

       :param data: The check_data set in add_check. This data must
                    be a dictionary that includes the keys
                    'regex' and 'message'.
       :type data:  dict

       :returns: error_data if the check fails, otherwise GUICheck.CHECK_OK.
    """
    if data['regex'].match(editable.get_text()):
        return GUICheck.CHECK_OK
    else:
        return data['message']
