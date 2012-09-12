# Text progress hub classes
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
# Red Hat Author(s): Jesse Keating <jkeating@redhat.com>
#

import time
import sys

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

from pyanaconda.flags import flags
from pykickstart.constants import KS_SHUTDOWN, KS_REBOOT

from pyanaconda.ui.tui.hubs import TUIHub
from pyanaconda.ui.tui.simpleline.base import ExitAllMainLoops

__all__ = ["ProgressHub"]

class ProgressHub(TUIHub):
    title = _("Installation Hub")

    def __init__(self, app, ksdata, storage, payload, instclass):
        TUIHub.__init__(self, app, ksdata, storage, payload, instclass)
        self._stepped = False

    def _update_progress(self):
        """Handle progress updates from install thread."""

        from pyanaconda import progress
        import Queue

        q = progress.progressQ

        # Grab all messages may have appeared since last time this method ran.
        while True:
            # Attempt to get a message out of the queue for how we should update
            # the progress bar.  If there's no message, don't error out.
            (code, args) = q.get()

            if code == progress.PROGRESS_CODE_INIT:
                # Text mode doesn't have a finite progress bar
                pass
            elif code == progress.PROGRESS_CODE_STEP:
                # Instead of updating a progress bar, we just print a pip
                # but print it without a new line.
                sys.stdout.write('.')
                sys.stdout.flush()
                # Use _stepped as an indication to if we need a newline before
                # the next message
                self._stepped = True
            elif code == progress.PROGRESS_CODE_MESSAGE:
                # This should already be translated
                if self._stepped:
                    # Get a new line in case we've done a step before
                    self._stepped = False
                    print('')
                print(args[0])
            elif code == progress.PROGRESS_CODE_COMPLETE:
                # There shouldn't be any more progress updates, so return
                q.task_done()


                if self._stepped:
                    print('')
                return True

            q.task_done()
        return True

    def refresh(self, args):
        from pyanaconda.install import doInstall, doConfiguration
        from pyanaconda.threads import threadMgr, AnacondaThread

        # We print this here because we don't really use the window object
        print(self.title)

        threadMgr.add(AnacondaThread(name="AnaInstallThread", target=doInstall,
                                     args=(self.storage, self.payload, self.data,
                                           self.instclass)))

        # This will run until we're all done with the install thread.
        self._update_progress()

        threadMgr.add(AnacondaThread(name="AnaConfigurationThread", target=doConfiguration,
                                     args=(self.storage, self.payload, self.data,
                                           self.instclass)))

        # This will run until we're all done with the configuration thread.
        self._update_progress()

        # kickstart install, continue automatically if reboot or shutdown selected
        if flags.automatedInstall and self.data.reboot.action in [KS_REBOOT, KS_SHUTDOWN]:
            # Just pretend like we got input, and our input doesn't care
            # what it gets, it just quits.
            self.input(None, None)
        
        return True

    def prompt(self, args = None):
        return(_("\tInstallation complete.  Press return to quit"))

    def input(self, args, key):
        # There is nothing to do here, just raise to exit the hub
        raise ExitAllMainLoops()
