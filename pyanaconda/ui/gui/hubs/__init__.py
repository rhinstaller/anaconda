# Base classes for Hubs.
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

import gi
gi.require_version("GLib", "2.0")

from gi.repository import GLib

from pyanaconda.flags import flags
from pyanaconda.i18n import _, C_
from pyanaconda.product import distributionText
from pyanaconda import lifecycle

from pyanaconda.ui import common
from pyanaconda.ui.gui import GUIObject
from pyanaconda.ui.gui.helpers import autoinstall_stopped
from pyanaconda.ui.gui.utils import gtk_call_once, escape_markup

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

class Hub(GUIObject, common.Hub):
    """A Hub is an overview UI screen.  A Hub consists of one or more grids of
       configuration options that the user may choose from.  Each grid is
       provided by a SpokeCategory, and each option is provided by a Spoke.
       When the user dives down into a Spoke and is finished interacting with
       it, they are returned to the Hub.

       Some Spokes are required.  The user must interact with all required
       Spokes before they are allowed to proceed to the next stage of
       installation.

       From a layout perspective, a Hub is the entirety of the screen, though
       the screen itself can be roughly divided into thirds.  The top third is
       some basic navigation information (where you are, what you're
       installing).  The middle third is the grid of Spokes.  The bottom third
       is an action area providing additional buttons (quit, continue) or
       progress information (during package installation).

       Installation may consist of multiple chained Hubs, or Hubs with
       additional standalone screens either before or after them.

       .. inheritance-diagram:: Hub
          :parts: 3
    """

    handles_autostep = True
    _hubs_collection = []

    def __init__(self, data, storage, payload, instclass):
        """Create a new Hub instance.

           The arguments this base class accepts defines the API that Hubs
           have to work with.  A Hub does not get free reign over everything
           in the anaconda class, as that would be a big mess.  Instead, a
           Hub may count on the following:

           ksdata       -- An instance of a pykickstart Handler object.  The
                           Hub uses this to populate its UI with defaults
                           and to pass results back after it has run.
           storage      -- An instance of storage.Storage.  This is useful for
                           determining what storage devices are present and how
                           they are configured.
           payload      -- An instance of a payload.Payload subclass.  This
                           is useful for displaying and selecting packages to
                           install, and in carrying out the actual installation.
           instclass    -- An instance of a BaseInstallClass subclass.  This
                           is useful for determining distribution-specific
                           installation information like default package
                           selections and default partitioning.
        """
        GUIObject.__init__(self, data)
        common.Hub.__init__(self, storage, payload, instclass)

        # enable the autoContinue feature if we are in kickstart
        # mode, but if the user interacts with the hub, it will be
        # disabled again
        self._autoContinue = flags.automatedInstall

        self._hubs_collection.append(self)
        self.timeout_id = None

        self._incompleteSpokes = []
        self._inSpoke = False
        self._notReadySpokes = []
        self._spokes = {}

        # Used to store the last result of _updateContinue
        self._warningMsg = None

        self._checker = None
        # Flag to indicate the user can continue even if the checker indicates an error.
        # The checker itself is left alone so the error message doesn't accidentally get
        # cleaered.
        self._checker_ignore = False

        self._spokesToStepIn = []
        self._spokeAutostepIndex = 0

    def _createBox(self):
        gi.require_version("Gtk", "3.0")
        gi.require_version("AnacondaWidgets", "3.3")

        from gi.repository import Gtk, AnacondaWidgets

        cats_and_spokes = self._collectCategoriesAndSpokes()
        categories = cats_and_spokes.keys()

        grid = Gtk.Grid(row_spacing=6, column_spacing=6, column_homogeneous=True,
                        margin_bottom=12)

        row = 0

        for c in sorted(categories, key=lambda c: c.title):
            obj = c()

            selectors = []
            for spokeClass in sorted(cats_and_spokes[c], key=lambda s: s.title):
                # Check if this spoke is to be shown in the supported environments
                if not any(spokeClass.should_run(environ, self.data) for environ in flags.environs):
                    continue

                # Create the new spoke and populate its UI with whatever data.
                # From here on, this Spoke will always exist.
                spoke = spokeClass(self.data, self.storage, self.payload, self.instclass)
                spoke.window.set_beta(self.window.get_beta())
                spoke.window.set_property("distribution", distributionText().upper())

                # If a spoke is not showable, it is unreachable in the UI.  We
                # might as well get rid of it.
                #
                # NOTE:  Any kind of spoke can be unshowable.
                if not spoke.showable:
                    del(spoke)
                    continue

                # This allows being able to jump between two spokes without
                # having to directly involve the hub.
                self._spokes[spokeClass.__name__] = spoke

                # If a spoke is indirect, it is reachable but not directly from
                # a hub.  This is for things like the custom partitioning spoke,
                # which you can only get to after going through the initial
                # storage configuration spoke.
                #
                # NOTE:  This only makes sense for NormalSpokes.  Other kinds
                # of spokes do not involve a hub.
                if spoke.indirect:
                    spoke.initialize()
                    continue

                spoke.selector = AnacondaWidgets.SpokeSelector(C_("GUI|Spoke", spoke.title),
                        spoke.icon)

                # Set all selectors to insensitive before initialize runs.  The call to
                # _updateCompleteness later will take care of setting it straight.
                spoke.selector.set_sensitive(False)
                spoke.initialize()

                if not spoke.ready:
                    self._notReadySpokes.append(spoke)

                # Set some default values on the associated selector that
                # affect its display on the hub.
                self._updateCompleteness(spoke, update_continue=False)
                spoke.selector.connect("button-press-event", self._on_spoke_clicked, spoke)
                spoke.selector.connect("key-release-event", self._on_spoke_clicked, spoke)

                # If this is a kickstart install, attempt to execute any provided ksdata now.
                if flags.automatedInstall and spoke.ready and spoke.changed and \
                   spoke.visitedSinceApplied:
                    spoke.execute()
                    spoke.visitedSinceApplied = False

                selectors.append(spoke.selector)

            if not selectors:
                continue

            label = Gtk.Label(label="<span font-desc=\"Sans 14\">%s</span>" % escape_markup(_(obj.title)),
                              use_markup=True, halign=Gtk.Align.START, margin_top=12, margin_bottom=12)
            grid.attach(label, 0, row, 2, 1)
            row += 1

            col = 0
            for selector in selectors:
                selector.set_margin_start(12)
                grid.attach(selector, col, row, 1, 1)
                col = int(not col)
                if col == 0:
                    row += 1

            # If this category contains an odd number of selectors, the above
            # row += 1 will not have run for the last row, which puts the next
            # category's title in the wrong place.
            if len(selectors) % 2:
                row += 1

        # initialization of all expected spokes has been started, so notify the controller
        hub_controller = lifecycle.get_controller_by_name(self.__class__.__name__)
        if hub_controller:
            hub_controller.all_modules_added()
        else:
            log.error("Initialization controller for hub %s expected but missing.", self.__class__.__name__)

        spokeArea = self.window.get_spoke_area()
        viewport = Gtk.Viewport()
        viewport.add(grid)
        spokeArea.add(viewport)

        self._updateContinue()

    def _updateCompleteness(self, spoke, update_continue=True):
        spoke.selector.set_sensitive(spoke.sensitive and spoke.ready)
        spoke.selector.set_property("status", spoke.status)
        spoke.selector.set_tooltip_markup(escape_markup(spoke.status))
        spoke.selector.set_incomplete(not spoke.completed and spoke.mandatory)
        self._handleCompleteness(spoke, update_continue)

    def _handleCompleteness(self, spoke, update_continue=True):
        # Add the spoke to the incomplete list if it's now incomplete, and make
        # sure it's not on the list if it's now complete.  Then show the box if
        # it's needed and hide it if it's not.
        if not spoke.mandatory or spoke.completed:
            if spoke in self._incompleteSpokes:
                self._incompleteSpokes.remove(spoke)
                log.debug("incomplete spokes: %s", self._incompleteSpokes)
        else:
            if spoke not in self._incompleteSpokes:
                self._incompleteSpokes.append(spoke)
                log.debug("incomplete spokes: %s", self._incompleteSpokes)

        if update_continue:
            self._updateContinue()

    def _updateContinue(self):
        warning = None
        if len(self._incompleteSpokes) == 0:
            if self._checker and not self._checker.check():
                warning = self._checker.error_message
                log.error(self._checker.error_message)

                # If this is a kickstart, consider the user to be warned and
                # let them continue anyway, manually
                if flags.automatedInstall:
                    self._autoContinue = False
                    self._checker_ignore = True
        else:
            warning = _("Please complete items marked with this icon before continuing to the next step.")

        # Check that this warning isn't already set to avoid spamming the
        # info bar with incomplete spoke messages when the hub starts
        if warning != self._warningMsg:
            self.clear_info()
            self._warningMsg = warning

            if warning:
                self.set_warning(warning)

        self._updateContinueButton()

    @property
    def continuePossible(self):
        return len(self._incompleteSpokes) == 0 and len(self._notReadySpokes) == 0 and (getattr(self._checker, "success", True) or self._checker_ignore)

    def _updateContinueButton(self):
        self.window.set_may_continue(self.continuePossible)

    def _update_spokes(self):
        from pyanaconda.ui.communication import hubQ
        import queue

        q = hubQ.q

        if not self._spokes and self.window.get_may_continue():
            # no spokes, move on
            log.debug("no spokes available on %s, continuing automatically", self)
            gtk_call_once(self.window.emit, "continue-clicked")

        click_continue = False
        # Grab all messages that may have appeared since last time this method ran.
        while True:
            try:
                (code, args) = q.get(False)
            except queue.Empty:
                break

            # The first argument to all codes is the name of the spoke we are
            # acting on.  If no such spoke exists, throw the message away.
            spoke = self._spokes.get(args[0], None)
            if not spoke or spoke.__class__.__name__ not in self._spokes:
                q.task_done()
                continue

            if code == hubQ.HUB_CODE_NOT_READY:
                self._updateCompleteness(spoke)

                if spoke not in self._notReadySpokes:
                    self._notReadySpokes.append(spoke)

                self._updateContinueButton()
                log.debug("spoke is not ready: %s", spoke)
            elif code == hubQ.HUB_CODE_READY:
                self._updateCompleteness(spoke)

                if spoke in self._notReadySpokes:
                    self._notReadySpokes.remove(spoke)

                self._updateContinueButton()
                log.debug("spoke is ready: %s", spoke)

                # If this is a real kickstart install (the kind with an input ks file)
                # and all spokes are now completed, we should skip ahead to the next
                # hub automatically.  Take into account the possibility the user is
                # viewing a spoke right now, though.
                if flags.automatedInstall:
                    spoke_title = spoke.title.replace("_", "")
                    # Users might find it helpful to know why a kickstart install
                    # went interactive.  Log that here.
                    if not spoke.completed and spoke.mandatory:
                        autoinstall_stopped("User interaction required on spoke %s" % spoke_title)
                    else:
                        log.debug("kickstart installation, spoke %s is ready", spoke_title)

                    # Spokes that were not initially ready got the execute call in
                    # _createBox skipped.  Now that it's become ready, do it.  Note
                    # that we also provide a way to skip this processing (see comments
                    # communication.py) to prevent getting caught in a loop.
                    if not args[1] and spoke.changed and spoke.visitedSinceApplied:
                        log.debug("execute spoke from event loop %s", spoke.title.replace("_", ""))
                        spoke.execute()
                        spoke.visitedSinceApplied = False

                    if self.continuePossible:
                        if self._inSpoke:
                            self._autoContinue = False
                        elif self._autoContinue:
                            click_continue = True

            elif code == hubQ.HUB_CODE_MESSAGE:
                spoke.selector.set_property("status", args[1])
                log.debug("setting %s status to: %s", spoke, args[1])

            q.task_done()

        # queue is now empty, should continue be clicked?
        if self._autoContinue and click_continue and self.window.get_may_continue():
            # enqueue the emit to the Gtk message queue
            log.debug("_autoContinue clicking continue button")
            gtk_call_once(self.window.emit, "continue-clicked")

        return True

    def refresh(self):
        GUIObject.refresh(self)
        self._createBox()

        for hub in Hub._hubs_collection:
            if hub.timeout_id is not None:
                log.debug("Disabling event loop for hub %s", hub.__class__.__name__)
                GLib.source_remove(hub.timeout_id)
                hub.timeout_id = None

        log.debug("Starting event loop for hub %s", self.__class__.__name__)
        self.timeout_id = GLib.timeout_add(100, self._update_spokes)

    ### SIGNAL HANDLERS

    def _on_spoke_clicked(self, selector, event, spoke):
        gi.require_version("Gdk", "3.0")
        from gi.repository import Gdk

        # This handler only runs for these two kinds of events, and only for
        # activate-type keys (space, enter) in the latter event's case.
        if event and not event.type in [Gdk.EventType.BUTTON_PRESS, Gdk.EventType.KEY_RELEASE]:
            return

        if event and event.type == Gdk.EventType.KEY_RELEASE and \
           event.keyval not in [Gdk.KEY_space, Gdk.KEY_Return, Gdk.KEY_ISO_Enter, Gdk.KEY_KP_Enter, Gdk.KEY_KP_Space]:
            return

        if selector:
            selector.grab_focus()

        # On automated kickstart installs, our desired behavior is to display
        # the hub while background processes work, then skip to the progress
        # hub immediately after everything's done.
        # However if the user proves his intent to change the kickstarted
        # values by entering any of the spokes, we need to disable the
        # autoContinue feature and wait for the user to explicitly state
        # that he is done configuring by pressing the continue button.
        self._autoContinue = False

        # Enter the spoke
        self._inSpoke = True
        spoke.refresh()
        self.main_window.enterSpoke(spoke)
        # the new spoke should be now visible, trigger the entered signal
        spoke.entered.emit(spoke)

    def spoke_done(self, spoke):
        # Ignore if not in a spoke
        if not self._inSpoke:
            return

        spoke.visitedSinceApplied = True

        # don't apply any actions if the spoke was visited automatically
        if spoke.automaticEntry:
            spoke.automaticEntry = False
            return

        # Don't take visitedSinceApplied into account here.  It will always be
        # True from the line above.
        if spoke.changed and (not spoke.skipTo or (spoke.skipTo and spoke.applyOnSkip)):
            spoke.apply()
            spoke.execute()
            spoke.visitedSinceApplied = False

        spoke.exited.emit(spoke)

        self._inSpoke = False

        # Now update the selector with the current status and completeness.
        for sp in self._spokes.values():
            if not sp.indirect:
                self._updateCompleteness(sp, update_continue=False)

        self._updateContinue()

        # And then if that spoke wants us to jump straight to another one,
        # handle that now.
        if spoke.skipTo and spoke.skipTo in self._spokes:
            dest = spoke.skipTo

            # Clear out the skipTo setting so we don't cycle endlessly.
            spoke.skipTo = None

            self._on_spoke_clicked(self._spokes[dest].selector, None, self._spokes[dest])
        # Otherwise, switch back to the hub (that's us!)
        else:
            self.main_window.returnToHub()

    def _doAutostep(self):
        """Autostep through all spokes managed by this hub"""
        log.info("autostepping through all spokes on hub %s", self.__class__.__name__)

        # create a list of all spokes in reverse alphabetic order, we will pop() from it when
        # processing all the spokes so the screenshots will actually be in alphabetic order
        self._spokesToStepIn = list(reversed(sorted(self._spokes.values(), key=lambda x: x.__class__.__name__)))

        # we can't just loop over all the spokes due to the asynchronous nature of GtkStack, so we start by
        # autostepping to the first spoke, this will trigger a callback that steps to the next spoke,
        # until we run out of unvisited spokes
        self._autostepSpoke()

    def _autostepSpoke(self):
        """Process a single spoke, if no more spokes are available report autostep as finished for the hub."""
        # do we have some spokes to work on ?
        if self._spokesToStepIn:
            # take one of them
            spoke = self._spokesToStepIn.pop()

            # increment the number of processed spokes
            self._spokeAutostepIndex += 1

            log.debug("stepping to spoke %s (%d/%d)", spoke.__class__.__name__, self._spokeAutostepIndex, len(self._spokes))

            # notify the spoke about the upcoming automatic entry and set a callback that will be called
            # once the spoke has been successfully processed
            spoke.automaticEntry = True
            spoke.autostepDoneCallback = lambda x: self._autostepSpoke()

            # if this is the last spoke, tell it to return to hub once processed
            if self._spokesToStepIn == []:
                spoke.lastAutostepSpoke = True
            gtk_call_once(self._on_spoke_clicked, None, None, spoke)
        else:
            log.info("autostep for hub %s finished", self.__class__.__name__)
            gtk_call_once(self._doPostAutostep)

    def _doPostAutostep(self):
        if self._spokesToStepIn:
            # there are still spokes that need to be stepped in
            return
        # we are done, re-emit the continue clicked signal we "consumed" previously
        # so that the Anaconda GUI can switch to the next screen (or quit)
        self.window.emit("continue-clicked")
