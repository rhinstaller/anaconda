# Summary text hub
#
# Copyright (C) 2012  Red Hat, Inc.
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

import sys
import time

from simpleline import App
from simpleline.render.prompt import Prompt
from simpleline.render.screen import InputState

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.i18n import N_, _
from pyanaconda.errors import CmdlineError
from pyanaconda.flags import flags
from pyanaconda.ui.lib.space import DirInstallSpaceChecker, FileSystemSpaceChecker
from pyanaconda.ui.tui.hubs import TUIHub

log = get_module_logger(__name__)

# TRANSLATORS: 'b' to begin installation
PROMPT_BEGIN_DESCRIPTION = N_("to begin installation")
PROMPT_BEGIN_KEY = 'b'


class SummaryHub(TUIHub):
    """
       .. inheritance-diagram:: SummaryHub
          :parts: 3
    """

    @staticmethod
    def get_screen_id():
        """Return a unique id of this UI screen."""
        return "installation-summary"

    def __init__(self, data, storage, payload):
        super().__init__(data, storage, payload)
        self.title = N_("Installation")

        if not conf.target.is_directory:
            self._checker = FileSystemSpaceChecker(payload)
        else:
            self._checker = DirInstallSpaceChecker(payload)

    def setup(self, args="anaconda"):
        environment = args
        should_schedule = TUIHub.setup(self, environment)
        if not should_schedule:
            return False

        if flags.automatedInstall:
            sys.stdout.write(_("Starting automated install"))
            sys.stdout.flush()
            spokes = self._spokes.values()

            while not all(spoke.ready for spoke in spokes):
                # Catch any asynchronous events (like storage crashing)
                loop = App.get_event_loop()
                loop.process_signals()
                sys.stdout.write('.')
                sys.stdout.flush()
                time.sleep(1)

            print('')

        return True

    # override the prompt so that we can skip user input on kickstarts
    # where all the data is in hand.  If not in hand, do the actual prompt.
    def prompt(self, args=None):
        incomplete_spokes = [spoke for spoke in self._spokes.values()
                            if spoke.mandatory and not spoke.completed]

        # Kickstart space check failure either stops the automated install or
        # raises an error when using cmdline mode.
        #
        # For non-cmdline, prompt for input but continue to treat it as an
        # automated install. The spokes (in particular software selection,
        # which expects an environment for interactive install) will continue
        # to behave the same, so the user can hit 'b' at the prompt and ignore
        # the warning.
        if flags.automatedInstall and not incomplete_spokes:

            # Check the available space.
            if flags.ksprompt and self._checker and not self._checker.check():

                # Space is not ok.
                print(self._checker.error_message)
                log.error(self._checker.error_message)

                # Unset the checker so everything passes next time.
                self._checker = None

                # TRANSLATORS: 'b' to begin installation
                print(_("Enter '%s' to ignore the warning and attempt to install anyway.") %
                      PROMPT_BEGIN_KEY)
            else:
                # Space is ok and spokes are complete, continue.
                self.close()
                return None

        # cmdline mode and incomplete spokes raises and error
        if not flags.ksprompt and incomplete_spokes:
            errtxt = _("The following mandatory spokes are not completed:") + \
                     "\n" + "\n".join(spoke.title for spoke in incomplete_spokes)
            log.error("CmdlineError: %s", errtxt)
            raise CmdlineError(errtxt)

        # if we ever need to halt the flow of a ks install to prompt users for
        # input, flip off the automatedInstall flag -- this way installation
        # does not automatically proceed once all spokes are complete, and a
        # user must confirm they want to begin installation
        if incomplete_spokes:
            flags.automatedInstall = False

        # override the default prompt
        prompt = super().prompt(args)
        # this screen cannot be closed
        prompt.remove_option(Prompt.CONTINUE)
        # offer the 'b' to begin installation option
        prompt.add_option(PROMPT_BEGIN_KEY, _(PROMPT_BEGIN_DESCRIPTION))
        return prompt

    def input(self, args, key):
        """Handle user input. Numbers are used to show a spoke, the rest is passed
        to the higher level for processing."""
        if self._container.process_user_input(key):
            return InputState.PROCESSED
        else:
            # If we get a continue, check for unfinished spokes.  If unfinished
            # don't continue
            if key == PROMPT_BEGIN_KEY:
                for spoke in self._spokes.values():
                    if not spoke.completed and spoke.mandatory:
                        print(_("Please complete all spokes before continuing"))
                        return InputState.DISCARDED
                # do a bit of final sanity checking, making sure pkg selection
                # size < available fs space
                if self._checker and not self._checker.check():
                    print(self._checker.error_message)
                    return InputState.DISCARDED

                return InputState.PROCESSED_AND_CLOSE
            elif key == Prompt.CONTINUE:
                # Kind of a hack, but we want to ignore if anyone presses 'c'
                # which is the global TUI key to close the current screen
                return InputState.DISCARDED
            else:
                return super().input(args, key)
