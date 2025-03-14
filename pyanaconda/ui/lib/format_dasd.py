#
# Copyright (C) 2017  Red Hat, Inc.
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
# Red Hat Author(s): Vendula Poncova <vponcova@redhat.com>
#
from blivet import arch

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.i18n import _
from pyanaconda.core.signal import Signal
from pyanaconda.flags import flags
from pyanaconda.modules.common.constants.objects import DASD, DEVICE_TREE
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.modules.common.structures.storage import DeviceData
from pyanaconda.modules.common.task import sync_run_task
from pyanaconda.ui.lib.storage import reset_storage

log = get_module_logger(__name__)


class DasdFormatting:
    """Class for formatting DASDs."""

    def __init__(self):
        self._dasds = []

        self._report = Signal()
        self._report.connect(log.debug)
        self._last_message = ""

        self._dasd_module = STORAGE.get_proxy(DASD)
        self._device_tree = STORAGE.get_proxy(DEVICE_TREE)

    @staticmethod
    def is_supported():
        """Is DASD formatting supported on this machine?"""
        return arch.is_s390()

    @property
    def report(self):
        """Signal for the progress reporting.

        Emits messages during the formatting.
        """
        return self._report

    @property
    def dasds(self):
        """List of found DASDs to format."""
        return self._dasds

    @property
    def dasds_summary(self):
        """Returns a string summary of DASDs to format."""
        return "\n".join(map(self.get_dasd_info, self.dasds))

    def get_dasd_info(self, disk_id):
        """Returns a string with description of a DASD."""
        data = DeviceData.from_structure(
            self._device_tree.GetDeviceData(disk_id)
        )
        return "{} ({})".format(data.path, data.attrs.get("bus-id"))

    def search_disks(self, disk_ids):
        """Search for a list of disks for DASDs to format."""
        self._dasds = self._dasd_module.FindFormattable(disk_ids)

    def should_run(self):
        """Should we run the formatting?"""
        return bool(self._dasds)

    def do_format(self):
        """Format with a remote task."""
        task_path = self._dasd_module.FormatWithTask(self._dasds)
        task_proxy = STORAGE.get_proxy(task_path)
        sync_run_task(task_proxy, callback=self._report_progress)

    def _report_progress(self, task_proxy):
        """Report progress of the remote task."""
        _step, msg = task_proxy.Progress

        if self._last_message != msg:
            self._last_message = msg
            self._report.emit(msg)

    def run(self):
        """Format all found DASDs and update the storage.

        This method could be run in a separate thread.
        """
        # Check if we have something to format.
        if not self._dasds:
            self.report.emit(_("Nothing to format"))
            return

        # Format all found DASDs.
        self.report.emit(_("Formatting DASDs"))
        self.do_format()

        # Update the storage.
        self.report.emit(_("Probing storage"))
        reset_storage()

    @staticmethod
    def run_automatically(disks, callback=None):
        """Run the DASD formatting automatically.

        This method could be run in a separate thread.
        """
        if not flags.automatedInstall:
            return

        if not DasdFormatting.is_supported():
            return

        formatting = DasdFormatting()
        formatting.search_disks(disks)

        if not formatting.should_run():
            return

        if callback:
            formatting.report.connect(callback)

        formatting.run()

        if callback:
            formatting.report.disconnect(callback)
