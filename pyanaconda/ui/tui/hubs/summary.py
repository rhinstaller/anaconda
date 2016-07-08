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

from pyanaconda.ui.lib.space import FileSystemSpaceChecker, DirInstallSpaceChecker
from pyanaconda.ui.tui.hubs import TUIHub
from pyanaconda.flags import flags
from pyanaconda.errors import CmdlineError
from pyanaconda.i18n import N_, _, C_
import sys
import time

import logging
log = logging.getLogger("anaconda")

class SummaryHub(TUIHub):
    """
       .. inheritance-diagram:: SummaryHub
          :parts: 3
    """
    title = N_("Installation")

    def __init__(self, app, data, storage, payload, instclass):
        super(SummaryHub, self).__init__(app, data, storage, payload, instclass)

        if not flags.dirInstall:
            self._checker = FileSystemSpaceChecker(storage, payload)
        else:
            self._checker = DirInstallSpaceChecker(storage, payload)

    def setup(self, environment="anaconda"):
        should_schedule = TUIHub.setup(self, environment=environment)
        if not should_schedule:
            return False

        if flags.automatedInstall:
            sys.stdout.write(_("Starting automated install"))
            sys.stdout.flush()
            spokes = self._keys.values()
            while not all(spoke.ready for spoke in spokes):
                # Catch any asyncronous events (like storage crashing)
                self._app.process_events()
                sys.stdout.write('.')
                sys.stdout.flush()
                time.sleep(1)

            print('')
            for spoke in spokes:
                if spoke.changed:
                    spoke.execute()

        return True

    # override the prompt so that we can skip user input on kickstarts
    # where all the data is in hand.  If not in hand, do the actual prompt.
    def prompt(self, args=None):
        incompleteSpokes = [spoke for spoke in self._keys.values()
                                      if spoke.mandatory and not spoke.completed]

        # Kickstart space check failure either stops the automated install or
        # raises an error when using cmdline mode.
        #
        # For non-cmdline, prompt for input but continue to treat it as an
        # automated install. The spokes (in particular software selection,
        # which expects an environment for interactive install) will continue
        # to behave the same, so the user can hit 'b' at the prompt and ignore
        # the warning.
        if flags.automatedInstall and self._checker and not self._checker.check():
            print(self._checker.error_message)
            log.error(self._checker.error_message)

            # Unset the checker so everything passes next time
            self._checker = None

            if not flags.ksprompt:
                return None
            else:
                # TRANSLATORS: 'b' to begin installation
                print(_("Enter '%s' to ignore the warning and attempt to install anyway.") %
                        # TRANSLATORS: 'b' to begin installation
                        C_("TUI|Spoke Navigation", "b")
                        )
        elif flags.automatedInstall and not incompleteSpokes:
            # Space is ok and spokes are complete, continue
            self.close()
            return None

        # cmdline mode and incomplete spokes raises and error
        if not flags.ksprompt and incompleteSpokes:
            errtxt = _("The following mandatory spokes are not completed:") + \
                     "\n" + "\n".join(spoke.title for spoke in incompleteSpokes)
            log.error("CmdlineError: %s", errtxt)
            raise CmdlineError(errtxt)

        # if we ever need to halt the flow of a ks install to prompt users for
        # input, flip off the automatedInstall flag -- this way installation
        # does not automatically proceed once all spokes are complete, and a
        # user must confirm they want to begin installation
        if incompleteSpokes:
            flags.automatedInstall = False

        # override the default prompt since we want to offer the 'b' to begin
        # installation option here
        return _("  Please make your choice from above ['%(quit)s' to quit | '%(begin)s' to begin installation |\n  '%(refresh)s' to refresh]: ") % {
            # TRANSLATORS: 'q' to quit
            'quit': C_('TUI|Spoke Navigation', 'q'),
            # TRANSLATORS: 'b' to begin installation
            'begin': C_('TUI|Spoke Navigation', 'b'),
            # TRANSLATORS: 'r' to refresh
            'refresh': C_('TUI|Spoke Navigation', 'r')
        }

    def input(self, args, key):
        """Handle user input. Numbers are used to show a spoke, the rest is passed
        to the higher level for processing."""
        try:
            number = int(key)
            self.app.switch_screen_with_return(self._keys[number])
            return None

        except (ValueError, KeyError):
            # If we get a continue, check for unfinished spokes.  If unfinished
            # don't continue
            # TRANSLATORS: 'b' to begin installation
            if key == C_('TUI|Spoke Navigation', 'b'):
                for spoke in self._spokes.values():
                    if not spoke.completed and spoke.mandatory:
                        print(_("Please complete all spokes before continuing"))
                        return False
                # do a bit of final sanity checking, making sure pkg selection
                # size < available fs space
                if self._checker and not self._checker.check():
                    print(self._checker.error_message)
                    return False
                if self.app._screens:
                    self.app.close_screen()
                    return True
            # TRANSLATORS: 'c' to continue
            elif key == C_('TUI|Spoke Navigation', 'c'):
                # Kind of a hack, but we want to ignore if anyone presses 'c'
                # which is the global TUI key to close the current screen
                return False
            else:
                return super(SummaryHub, self).input(args, key)
