# Base classes for Hubs.
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

from pyanaconda.ui.gui import UIObject
from pyanaconda.ui.gui.categories import collect_categories
from pyanaconda.ui.gui.spokes import StandaloneSpoke, collect_spokes

class Hub(UIObject):
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
    """

    def __init__(self, data, devicetree, instclass):
        """Create a new Hub instance.

           The arguments this base class accepts defines the API that Hubs
           have to work with.  A Hub does not get free reign over everything
           in the anaconda class, as that would be a big mess.  Instead, a
           Hub may count on the following:

           ksdata       -- An instance of a pykickstart Handler object.  The
                           Hub uses this to populate its UI with defaults
                           and to pass results back after it has run.
           devicetree   -- An instance of storage.devicetree.DeviceTree.  This
                           is useful for determining what storage devices are
                           present and how they are configured.
           instclass    -- An instance of a BaseInstallClass subclass.  This
                           is useful for determining distribution-specific
                           installation information like default package
                           selections and default partitioning.
        """
        UIObject.__init__(self, data)

        self._incompleteSpokes = []
        self._selectors = {}

        self.devicetree = devicetree
        self.instclass = instclass

    def _runSpoke(self, action):
        from gi.repository import Gtk

        action.setup()

        # Set various properties on the new Spoke based upon what was set
        # on the Hub.
        action.window.set_beta(self.window.get_beta())
        action.window.set_property("distribution", self.window.get_property("distribution"))

        action.window.show_all()

        # Start a recursive main loop for this spoke, which will prevent
        # signals from going to the underlying (but still displayed) Hub and
        # prevent the user from switching away.  It's up to the spoke's back
        # button handler to kill its own layer of main loop.
        Gtk.main()
        action.apply()

    def _createBox(self):
        from gi.repository import Gtk, AnacondaWidgets

        # Collect all the categories this hub displays, then collect all the
        # spokes belonging to all those categories.
        categories = sorted(filter(lambda c: c.displayOnHub == self.__class__, collect_categories()),
                            key=lambda c: c.title)

        box = Gtk.VBox(False, 6)

        for c in categories:
            obj = c()

            selectors = []
            for spokeClass in collect_spokes(obj.__class__.__name__):
                # Create the new spoke and populate its UI with whatever data.
                # From here on, this Spoke will always exist.
                spoke = spokeClass(self.data, self.devicetree, self.instclass)
                spoke.populate()

                if not spoke.showable:
                    continue

                # And then create its associated selector, and set some default
                # values that affect its display on the hub.
                selector = AnacondaWidgets.SpokeSelector(spoke.title, spoke.icon)
                selector.set_property("status", spoke.status)
                selector.set_incomplete(not spoke.completed)
                self._handleCompleteness(spoke)
                selector.connect("button-press-event", self._on_spoke_clicked)

                selectors.append(selector)

                # These settings are a way of being able to jump between two
                # spokes without having to involve the hub (directly).
                self._selectors[spokeClass.__name__] = selector
                selector.spoke = spoke

            if not selectors:
                continue

            label = Gtk.Label("<span font-desc=\"Sans 14\">%s</span>" % obj.title)
            label.set_use_markup(True)
            label.set_halign(Gtk.Align.START)
            label.set_margin_bottom(12)
            box.pack_start(label, False, True, 0)

            grid = obj.grid(selectors)
            grid.set_margin_left(12)
            box.pack_start(grid, False, True, 0)

        spokeArea = self.window.get_spoke_area()
        spokeArea.add_with_viewport(box)

    def _handleCompleteness(self, spoke):
        from gi.repository import Gtk

        # Add the spoke to the incomplete list if it's now incomplete, and make
        # sure it's not on the list if it's now complete.  Then show the box if
        # it's needed and hide it if it's not.
        if spoke.completed:
            if spoke in self._incompleteSpokes:
                self._incompleteSpokes.remove(spoke)
        else:
            if spoke not in self._incompleteSpokes:
                self._incompleteSpokes.append(spoke)

        if len(self._incompleteSpokes) == 0:
            self.window.clear_info()
        else:
            self.window.set_info(Gtk.MessageType.WARNING, "Please complete items marked with this icon first.")

    def setup(self):
        UIObject.setup(self)
        self._createBox()

    ### SIGNAL HANDLERS

    def register_event_cb(self, event, cb):
        if event == "continue" and hasattr(self, "continueButton"):
            self.continueButton.connect("clicked", lambda *args: cb())
        elif event == "quit" and hasattr(self, "quitButton"):
            self.quitButton.connect("clicked", lambda *args: cb())

    def _on_spoke_clicked(self, selector, event):
        spoke = selector.spoke

        self._runSpoke(spoke)

        # Now update the selector with the current status and completeness.
        selector.set_property("status", spoke.status)
        selector.set_incomplete(not spoke.completed)

        self._handleCompleteness(spoke)

        # And then if that spoke wants us to jump straight to another one,
        # handle that now.
        if spoke.skipTo and spoke.skipTo in self._selectors:
            dest = spoke.skipTo

            # Clear out the skipTo setting so we don't cycle endlessly.
            spoke.skipTo = None

            self._on_spoke_clicked(self._selectors[dest], None)
