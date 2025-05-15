#
# Copyright (C) 2011-2013  Red Hat, Inc.
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
import sys

from pykickstart.constants import KS_REBOOT, KS_SHUTDOWN

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core import util
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import IPMI_FINISHED, THREAD_INSTALL
from pyanaconda.core.i18n import C_, _
from pyanaconda.core.timer import Timer
from pyanaconda.flags import flags
from pyanaconda.product import productName
from pyanaconda.ui.gui.hubs.summary import SummaryHub
from pyanaconda.ui.gui.spokes import StandaloneSpoke
from pyanaconda.ui.gui.utils import gtk_call_once

log = get_module_logger(__name__)

__all__ = ["ProgressSpoke"]


class ProgressSpoke(StandaloneSpoke):
    """
       .. inheritance-diagram:: ProgressSpoke
          :parts: 3
    """

    builderObjects = ["progressWindow"]
    mainWidgetName = "progressWindow"
    uiFile = "spokes/installation_progress.glade"
    postForHub = SummaryHub
    hide_help_button = True

    @staticmethod
    def get_screen_id():
        """Return a unique id of this UI screen."""
        return "installation-progress"

    def __init__(self, data, storage, payload):
        super().__init__(data, storage, payload)
        self._totalSteps = 0
        self._currentStep = 0
        self._update_progress_timer = Timer()

        self._progressBar = self.builder.get_object("progressBar")
        self._progressLabel = self.builder.get_object("progressLabel")
        self._progressNotebook = self.builder.get_object("progressNotebook")
        self._spinner = self.builder.get_object("progressSpinner")

    @property
    def completed(self):
        """This spoke is never completed, initially."""
        return False

    def apply(self):
        """There is nothing to apply."""
        pass

    def _update_progress(self, callback=None):
        import queue

        from pyanaconda.progress import progressQ

        q = progressQ.q

        # Grab all messages may have appeared since last time this method ran.
        while True:
            # Attempt to get a message out of the queue for how we should update
            # the progress bar.  If there's no message, don't error out.
            try:
                (code, args) = q.get(False)
            except queue.Empty:
                break

            if code == progressQ.PROGRESS_CODE_INIT:
                self._init_progress_bar(args[0])
            elif code == progressQ.PROGRESS_CODE_STEP:
                self._step_progress_bar()
            elif code == progressQ.PROGRESS_CODE_MESSAGE:
                self._update_progress_message(args[0])
            elif code == progressQ.PROGRESS_CODE_COMPLETE:
                q.task_done()

                # we are done, stop the progress indication
                gtk_call_once(self._progressBar.set_fraction, 1.0)
                gtk_call_once(self._progressLabel.set_text, _("Complete!"))
                gtk_call_once(self._spinner.stop)
                gtk_call_once(self._spinner.hide)

                if callback:
                    callback()

                # There shouldn't be any more progress bar updates, so return False
                # to indicate this method should be removed from the idle loop.
                return False
            elif code == progressQ.PROGRESS_CODE_QUIT:
                sys.exit(args[0])

            q.task_done()

        return True

    def _installation_done(self):
        log.debug("The installation has finished.")
        util.ipmi_report(IPMI_FINISHED)

        if conf.license.eula:
            self.set_warning(_("Use of this product is subject to the license agreement "
                               "found at %s") % conf.license.eula)
            self.window.show_all()

        # Show the reboot message.
        self._progressNotebook.set_current_page(1)

        # Enable the continue button.
        self.window.set_may_continue(True)

        # Hide the quit button.
        quit_button = self.window.get_quit_button()
        quit_button.hide()

        # kickstart install, continue automatically if reboot or shutdown selected
        if flags.automatedInstall and self.data.reboot.action in [KS_REBOOT, KS_SHUTDOWN]:
            self.window.emit("continue-clicked")

    def initialize(self):
        super().initialize()
        # Disable the continue button.
        self.window.set_may_continue(False)

        # Set the label of the continue button.
        if conf.target.is_hardware and conf.system.can_reboot:
            continue_label = C_("GUI|Progress", "_Reboot System")
        else:
            continue_label = C_("GUI|Progress", "_Finish Installation")

        continue_button = self.window.get_continue_button()
        continue_button.set_label(continue_label)

        # Set the reboot label.
        if conf.target.is_hardware:
            continue_text = _(
                "%s is now successfully installed and ready for you to use!\n"
                "Go ahead and reboot your system to start using it!"
            ) % productName
        else:
            continue_text = _(
                "%s is now successfully installed and ready for you to use!\n"
                "Go ahead and quit the application to start using it!"
            ) % productName

        label = self.builder.get_object("rebootLabel")
        label.set_text(continue_text)

        # Don't show the reboot message.
        self._progressNotebook.set_current_page(0)

    def refresh(self):
        from pyanaconda.installation import run_installation
        from pyanaconda.threading import AnacondaThread, threadMgr
        super().refresh()

        self._update_progress_timer.timeout_msec(
            250,
            self._update_progress,
            self._installation_done
        )

        threadMgr.add(AnacondaThread(
            name=THREAD_INSTALL,
            target=run_installation,
            args=(self.payload, self.data))
        )

        log.debug("The installation has started.")

    def _init_progress_bar(self, steps):
        self._totalSteps = steps
        self._currentStep = 0

        gtk_call_once(self._progressBar.set_fraction, 0.0)

    def _step_progress_bar(self):
        if not self._totalSteps:
            return

        self._currentStep += 1
        gtk_call_once(self._progressBar.set_fraction, self._currentStep/self._totalSteps)

    def _update_progress_message(self, message):
        if not self._totalSteps:
            return

        gtk_call_once(self._progressLabel.set_text, message)
