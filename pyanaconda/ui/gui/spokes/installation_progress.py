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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
from pykickstart.constants import KS_REBOOT, KS_SHUTDOWN

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core import util
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import IPMI_FINISHED
from pyanaconda.core.i18n import C_, _
from pyanaconda.core.product import get_product_name
from pyanaconda.flags import flags
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

    @staticmethod
    def get_screen_id():
        """Return a unique id of this UI screen."""
        return "installation-progress"

    def __init__(self, data, storage, payload):
        super().__init__(data, storage, payload)
        self._progressBar = self.builder.get_object("progressBar")
        self._progressLabel = self.builder.get_object("progressLabel")
        self._progressNotebook = self.builder.get_object("progressNotebook")
        self._spinner = self.builder.get_object("progressSpinner")
        self._task_proxy = None

    @property
    def completed(self):
        """This spoke is never completed, initially."""
        return False

    def apply(self):
        """There is nothing to apply."""
        pass

    def _on_installation_done(self):
        log.debug("The installation has finished.")

        # Stop the spinner.
        gtk_call_once(self._spinner.stop)
        gtk_call_once(self._spinner.hide)

        # Finish the installation task. Re-raise tracebacks if any.
        self._task_proxy.Finish()

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
            ) % get_product_name()
        else:
            continue_text = _(
                "%s is now successfully installed and ready for you to use!\n"
                "Go ahead and quit the application to start using it!"
            ) % get_product_name()

        label = self.builder.get_object("rebootLabel")
        label.set_text(continue_text)

        # Don't show the reboot message.
        self._progressNotebook.set_current_page(0)

    def refresh(self):
        from pyanaconda.core.dbus import DBus
        from pyanaconda.core.threads import thread_manager
        from pyanaconda.modules.common.constants.services import BOSS

        super().refresh()

        # Wait for background threads to finish
        if thread_manager.running > 1:
            log.debug("Waiting for %s threads to finish...", thread_manager.running - 1)
            for name in thread_manager.names:
                log.debug("Thread %s is still running", name)
            thread_manager.wait_all()
            log.debug("No more threads are running, continuing with installation.")

        # Initialize the progress bar
        gtk_call_once(self._progressBar.set_fraction, 0.0)

        # Start the installation task via D-Bus
        boss_proxy = BOSS.get_proxy()
        task_path = boss_proxy.InstallWithTasks()[0]
        self._task_proxy = DBus.get_proxy(BOSS.service_name, task_path)

        self._task_proxy.ProgressChanged.connect(self._on_progress_changed)
        self._task_proxy.Stopped.connect(self._on_installation_done)

        self._task_proxy.Start()

        # Start the spinner
        gtk_call_once(self._spinner.start)

        log.debug("The installation has started.")

    def _on_progress_changed(self, step, message):
        """Handle a new progress report."""
        if message:
            gtk_call_once(self._progressLabel.set_text, message)

        if self._task_proxy.Steps > 0:
            gtk_call_once(self._progressBar.set_fraction, step/self._task_proxy.Steps)
