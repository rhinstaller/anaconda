# The base classes for Anaconda TUI Hubs
#
# Copyright (C) (2012)  Red Hat, Inc.
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
from pyanaconda import ihelp
from pyanaconda import lifecycle
from pyanaconda.constants_text import INPUT_PROCESSED, INPUT_DISCARDED
from pyanaconda.ui.tui import simpleline as tui
from pyanaconda.ui.tui.tuiobject import TUIObject, HelpScreen
from pyanaconda.ui import common

from pyanaconda.i18n import _, N_
from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

class TUIHub(TUIObject, common.Hub):
    """Base Hub class implementing the pyanaconda.ui.common.Hub interface.
       It uses text based categories to look for relevant Spokes and manages
       all the spokes it finds to have the proper category.

       :param categories: list all the spoke categories to be displayed in this Hub
       :type categories: list of strings

       :param title: title for this Hub
       :type title: str

       .. inheritance-diagram:: TUIHub
          :parts: 3
    """

    categories = []
    title = N_("Default HUB title")

    def __init__(self, app, data, storage, payload, instclass):
        TUIObject.__init__(self, app, data)
        common.Hub.__init__(self, storage, payload, instclass)

        self._spokes = {}     # holds spokes referenced by their class name
        self._keys = {}       # holds spokes referenced by their user input key
        self._spoke_count = 0

    def setup(self, environment="anaconda"):
        cats_and_spokes = self._collectCategoriesAndSpokes()
        categories = cats_and_spokes.keys()

        for c in sorted(categories, key=lambda c: c.title):

            for spokeClass in sorted(cats_and_spokes[c], key=lambda s: s.title):
                # Check if this spoke is to be shown in anaconda
                if not spokeClass.should_run(environment, self.data):
                    continue

                spoke = spokeClass(self.app, self.data, self.storage, self.payload, self.instclass)

                if spoke.showable:
                    spoke.initialize()
                else:
                    del spoke
                    continue

                if spoke.indirect:
                    continue

                self._spoke_count += 1
                self._keys[self._spoke_count] = spoke
                self._spokes[spokeClass.__name__] = spoke

        if self._spoke_count:
            # initialization of all expected spokes has been started, so notify the controller
            hub_controller = lifecycle.get_controller_by_name(self.__class__.__name__)
            if hub_controller:
                hub_controller.all_modules_added()
            else:
                log.error("Initialization controller for hub %s expected but missing.", self.__class__.__name__)

        # only schedule the hub if it has some spokes
        return self._spoke_count != 0

    def refresh(self, args=None):
        """This methods fills the self._window list by all the objects
        we want shown on this screen. Title and Spokes mostly."""
        TUIObject.refresh(self, args)

        def _prep(i, w):
            number = tui.TextWidget("%2d)" % i)
            return tui.ColumnWidget([(3, [number]), (None, [w])], 1)

        # split spokes to two columns
        left = [_prep(i, w) for i, w in self._keys.items() if i % 2 == 1]
        right = [_prep(i, w) for i, w in self._keys.items() if i % 2 == 0]

        c = tui.ColumnWidget([(39, left), (39, right)], 2)
        self._window += [c, ""]

        return True

    def input(self, args, key):
        """Handle user input. Numbers are used to show a spoke, the rest is passed
        to the higher level for processing."""

        try:
            number = int(key)
            self.app.switch_screen_with_return(self._keys[number])
            return INPUT_PROCESSED

        except (ValueError, KeyError):
            # If we get a continue, check for unfinished spokes.  If unfinished
            # don't continue
            # TRANSLATORS: 'c' to continue
            if key == tui.Prompt.CONTINUE:
                for spoke in self._spokes.values():
                    if not spoke.completed and spoke.mandatory:
                        print(_("Please complete all spokes before continuing"))
                        return INPUT_DISCARDED
            # TRANSLATORS: 'h' to help
            elif key == tui.Prompt.HELP:
                if self.has_help:
                    help_path = ihelp.get_help_path(self.helpFile, self.instclass, True)
                    self.app.switch_screen_modal(HelpScreen(self.app, help_path))
                    return INPUT_PROCESSED
            return key

    def prompt(self, args=None):
        """Show an alternative prompt if the hub contains only one spoke.
        Otherwise it is not readily apparent that the user needs to press
        1 to enter the single visible spoke.

        :param args: optional argument passed from switch_screen calls
        :type args: anything

        :return: returns text to be shown next to the prompt for input or None
                 to skip further input processing
        :rtype: str|None
        """
        prompt = super(TUIHub, self).prompt(args)

        if self._spoke_count == 1:
            prompt.add_option("1", _("to enter the %(spoke_title)s spoke") % {"spoke_title": list(self._spokes.values())[0].title})

        if self.has_help:
            prompt.add_help_option()

        return prompt
