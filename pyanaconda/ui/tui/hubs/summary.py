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
# Red Hat Author(s): Martin Sivak <msivak@redhat.com>
#                    Jesse Keating <jkeating@redhat.com>
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

        # do a bit of final sanity checking, make sure pkg selection
        # size < available fs space
        if flags.automatedInstall:
            if self._checker and not self._checker.check():
                print(self._checker.error_message)
            if not incompleteSpokes:
                self.close()
                return None

        if flags.ksprompt:
            for spoke in incompleteSpokes:
                log.info("kickstart installation stopped for info: %s", spoke.title)
        else:
            errtxt = _("The following mandatory spokes are not completed:") + \
                     "\n" + "\n".join(spoke.title for spoke in incompleteSpokes)
            log.error("CmdlineError: %s", errtxt)
            raise CmdlineError(errtxt)


        # override the default prompt since we want to offer the 'b' to begin
        # installation option here
        return _("  Please make your choice from above ['q' to quit | 'b' to begin installation |\n  'r' to refresh]: ")

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
                super(SummaryHub, self).input(args, key)
