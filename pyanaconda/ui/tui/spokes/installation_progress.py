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

import sys

from pykickstart.constants import KS_REBOOT, KS_SHUTDOWN
from simpleline import App
from simpleline.event_loop import ExitMainLoop
from simpleline.render.prompt import Prompt

from pyanaconda.core import util
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import IPMI_FINISHED, THREAD_INSTALL
from pyanaconda.core.i18n import N_, _
from pyanaconda.flags import flags
from pyanaconda.ui.tui.hubs.summary import SummaryHub
from pyanaconda.ui.tui.spokes import StandaloneTUISpoke

__all__ = ["ProgressSpoke"]


class ProgressSpoke(StandaloneTUISpoke):
    """
       .. inheritance-diagram:: ProgressSpoke
          :parts: 3
    """
    postForHub = SummaryHub

    @staticmethod
    def get_screen_id():
        """Return a unique id of this UI screen."""
        return "installation-progress"

    def __init__(self, ksdata, storage, payload):
        self.initialize_start()
        super().__init__(ksdata, storage, payload)
        self.title = N_("Progress")
        self._stepped = False
        self.initialize_done()

    @property
    def completed(self):
        # this spoke is never completed, initially
        return False

    def _update_progress(self):
        """Handle progress updates from install thread."""

        import queue

        from pyanaconda.progress import progressQ

        q = progressQ.q

        # Grab all messages may have appeared since last time this method ran.
        while True:
            # Attempt to get a message out of the queue for how we should update
            # the progress bar.  If there's no message, don't error out.
            # Also flush the communication Queue at least once a second and
            # process it's events so we can react to async evens (like a thread
            # throwing an exception)
            while True:
                try:
                    (code, args) = q.get(timeout=1)
                    break
                except queue.Empty:
                    pass
                finally:
                    loop = App.get_event_loop()
                    loop.process_signals()

            if code == progressQ.PROGRESS_CODE_INIT:
                # Text mode doesn't have a finite progress bar
                pass
            elif code == progressQ.PROGRESS_CODE_STEP:
                # Instead of updating a progress bar, we just print a pip
                # but print it without a new line.
                print('.', flush=True, end='')
                # Use _stepped as an indication to if we need a newline before
                # the next message
                self._stepped = True
            elif code == progressQ.PROGRESS_CODE_MESSAGE:
                # This should already be translated
                if self._stepped:
                    # Get a new line in case we've done a step before
                    self._stepped = False
                    print('')
                # Print the progress message.
                print(args[0], flush=True)
            elif code == progressQ.PROGRESS_CODE_COMPLETE:
                # There shouldn't be any more progress updates, so return
                q.task_done()

                if self._stepped:
                    print('')
                return True
            elif code == progressQ.PROGRESS_CODE_QUIT:
                sys.exit(args[0])

            q.task_done()
        return True

    def show_all(self):
        super().show_all()
        from pyanaconda.installation import run_installation
        from pyanaconda.threading import AnacondaThread, threadMgr

        threadMgr.add(AnacondaThread(
            name=THREAD_INSTALL,
            target=run_installation,
            args=(self.payload, self.data))
        )

        # This will run until we're all done with the install thread.
        self._update_progress()

        util.ipmi_report(IPMI_FINISHED)

        if conf.license.eula:
            # Notify user about the EULA (if any).
            print(_("Installation complete"))
            print('')
            print(_("Use of this product is subject to the license agreement found at:"))
            print(conf.license.eula)
            print('')

        # kickstart install, continue automatically if reboot or shutdown selected
        if flags.automatedInstall and self.data.reboot.action in [KS_REBOOT, KS_SHUTDOWN]:
            # Just pretend like we got input, and our input doesn't care
            # what it gets, it just quits.
            raise ExitMainLoop()

    def prompt(self, args=None):
        return Prompt(_("Installation complete. Press %s to quit") % Prompt.ENTER)

    def input(self, args, key):
        # There is nothing to do here, just raise to exit the spoke
        raise ExitMainLoop()

    # Override Spoke.apply
    def apply(self):
        pass
