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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from pyanaconda import lifecycle
from pyanaconda.ui.tui.tuiobject import TUIObject
from pyanaconda.ui.lib.help import get_help_path_for_screen
from pyanaconda.ui import common

from simpleline.render.adv_widgets import HelpScreen
from simpleline.render.containers import ListRowContainer
from simpleline.render.prompt import Prompt
from simpleline.render.screen import InputState
from simpleline.render.screen_handler import ScreenHandler

from pyanaconda.core.i18n import _, N_
from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class TUIHub(TUIObject, common.Hub):
    """Base Hub class implementing the pyanaconda.ui.common.Hub interface.
       It uses text based categories to look for relevant Spokes and manages
       all the spokes it finds to have the proper category.

       :param categories: list all the spoke categories to be displayed in this Hub
       :type categories: list of strings



       .. inheritance-diagram:: TUIHub
          :parts: 3
    """

    categories = []

    def __init__(self, data, storage, payload):
        TUIObject.__init__(self, data)
        common.Hub.__init__(self, storage, payload)
        self.title = N_("Default HUB title")
        self._container = None

        self._spokes_map = []  # hold all the spokes in the right ordering
        self._spokes = {}      # holds spokes referenced by their class name
        self._spoke_count = 0

        # we want user input
        self.input_required = True

    def setup(self, args="anaconda"):
        TUIObject.setup(self, args)
        environment = args
        cats_and_spokes = self._collectCategoriesAndSpokes()
        categories = cats_and_spokes.keys()

        # display categories by sort order or class name if their
        # sort order is the same
        for c in common.sort_categories(categories):

            hub_spokes = []
            for spoke_class in cats_and_spokes[c]:
                # Do the checks for the spoke and create the spoke
                if spoke_class.should_run(environment, self.data):
                    spoke = spoke_class(self.data, self.storage, self.payload)

                    if spoke.showable:
                        spoke.initialize()
                    else:
                        log.warning("Spoke %s initialization failure!", spoke.__class__.__name__)
                        del spoke
                        continue

                    if spoke.indirect:
                        continue

                    hub_spokes.append(spoke)

            # sort created spokes and add them to result structures
            for spoke in sorted(hub_spokes, key=lambda s: s.title):

                self._spoke_count += 1
                self._spokes_map.append(spoke)
                self._spokes[spoke.__class__.__name__] = spoke

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
        """This methods fills the self.window list by all the objects
        we want shown on this screen. Title and Spokes mostly."""
        TUIObject.refresh(self, args)

        self._container = ListRowContainer(2, columns_width=39, spacing=2)

        for w in self._spokes_map:
            self._container.add(w, callback=self._item_called, data=w)

        self.window.add_with_separator(self._container)

    def _item_called(self, data):
        item = data
        ScreenHandler.push_screen(item)

    def _get_help(self):
        """Get the help path for this screen."""
        return get_help_path_for_screen(self.get_screen_id())

    def input(self, args, key):
        """Handle user input. Numbers are used to show a spoke, the rest is passed
        to the higher level for processing."""

        if self._container.process_user_input(key):
            return InputState.PROCESSED
        else:
            # If we get a continue, check for unfinished spokes.  If unfinished
            # don't continue
            if key == Prompt.CONTINUE:
                for spoke in self._spokes.values():
                    if not spoke.completed and spoke.mandatory:
                        print(_("Please complete all spokes before continuing"))
                        return InputState.DISCARDED
            elif key == Prompt.HELP:
                help_path = self._get_help()

                if help_path:
                    ScreenHandler.push_screen_modal(HelpScreen(help_path))
                    return InputState.PROCESSED_AND_REDRAW

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
        prompt = super().prompt(args)

        if self._spoke_count == 1:
            prompt.add_option("1", _("to enter the %(spoke_title)s spoke") % {"spoke_title": list(self._spokes.values())[0].title})

        if self._get_help():
            prompt.add_help_option()

        return prompt
