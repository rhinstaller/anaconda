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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.flags import flags
from pyanaconda.core.i18n import N_, _
from pyanaconda.core import util
from pyanaconda.core.constants import IPMI_FINISHED
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.ui.tui.spokes import StandaloneTUISpoke
from pyanaconda.ui.tui.hubs.summary import SummaryHub

from simpleline import App
from simpleline.render.prompt import Prompt
from simpleline.event_loop import ExitMainLoop, AbstractSignal

from pykickstart.constants import KS_SHUTDOWN, KS_REBOOT

log = get_module_logger(__name__)

__all__ = ["ProgressSpoke"]


class ScreenReadySignal(AbstractSignal):
    """The current screen is ready."""


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
        self._task = None
        self._stepped = False
        self.initialize_done()

    @property
    def completed(self):
        # this spoke is never completed, initially
        return False

    def _on_progress_changed(self, step, message):
        """Handle a new progress report."""
        if message:
            # Print a new line in case we've done a step.
            if self._stepped:
                print('')

            # Print the progress message.
            # It should already be translated.
            print(message, flush=True)

            # Don't print a new line before the next message.
            self._stepped = False
        else:
            # Instead of updating a progress bar, we just
            # print a pip but print it without a new line.
            print('.', flush=True, end='')

            # Use _stepped as an indication to if we need
            # a newline before the next message.
            self._stepped = True

    def show_all(self):
        super().show_all()
        from pyanaconda.installation import RunInstallationTask

        # Start the installation task.
        self._task = RunInstallationTask(
            payload=self.payload,
            ksdata=self.data
        )
        self._task.progress_changed_signal.connect(
            self._on_progress_changed
        )
        self._task.stopped_signal.connect(
            self._on_installation_done
        )
        self._task.start()

        log.debug("The installation has started.")

        # This will run until the task is finished.
        loop = App.get_event_loop()
        loop.process_signals(return_after=ScreenReadySignal)

        # kickstart install, continue automatically if reboot or shutdown selected
        if flags.automatedInstall and self.data.reboot.action in [KS_REBOOT, KS_SHUTDOWN]:
            # Just pretend like we got input, and our input doesn't care
            # what it gets, it just quits.
            raise ExitMainLoop()

    def _on_installation_done(self):
        log.debug("The installation has finished.")

        # Print a new line after the last step.
        if self._stepped:
            print('')

        # Finish the installation task. Re-raise tracebacks if any.
        self._task.finish()

        util.ipmi_report(IPMI_FINISHED)

        if conf.license.eula:
            # Notify user about the EULA (if any).
            print(_("Installation complete"))
            print('')
            print(_("Use of this product is subject to the license agreement found at:"))
            print(conf.license.eula)
            print('')

        loop = App.get_event_loop()
        loop.enqueue_signal(ScreenReadySignal(self))

    def prompt(self, args=None):
        return Prompt(_("Installation complete. Press %s to quit") % Prompt.ENTER)

    def input(self, args, key):
        # There is nothing to do here, just raise to exit the spoke
        raise ExitMainLoop()

    # Override Spoke.apply
    def apply(self):
        pass
