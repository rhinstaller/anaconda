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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Vendula Poncova <vponcova@redhat.com>
#

import gi
gi.require_version("BlockDev", "2.0")
from gi.repository import BlockDev as blockdev

from blivet import arch

from pyanaconda.flags import flags
from pyanaconda.ui.lib.disks import getDisks
from pyanaconda.core.isignal import Signal
from pyanaconda.storage_utils import on_disk_storage
from pyanaconda.core.i18n import _
from pyanaconda.storage.osinstall import storage_initialize

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class DasdFormatting(object):
    """Class for formatting DASDs."""

    def __init__(self):
        self._dasds = []

        self._can_format_unformatted = True
        self._can_format_ldl = True

        self._report = Signal()
        self._report.connect(log.debug)

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

    def get_dasd_info(self, disk):
        """Returns a string with description of a DASD."""
        return "/dev/" + disk.name + " (" + disk.busid + ")"

    def _is_dasd(self, disk):
        """Is it a DASD disk?"""
        return disk.type == "dasd"

    def _is_unformatted_dasd(self, disk):
        """Is it an unformatted DASD?"""
        return self._is_dasd(disk) and blockdev.s390.dasd_needs_format(disk.busid)

    def _is_ldl_dasd(self, disk):
        """Is it an LDL DASD?"""
        return self._is_dasd(disk) and blockdev.s390.dasd_is_ldl(disk.name)

    def _get_unformatted_dasds(self, disks):
        """Returns a list of unformatted DASDs."""
        result = []

        if not self._can_format_unformatted:
            log.debug("We are not allowed to format unformatted DASDs.")
            return result

        for disk in disks:
            if self._is_unformatted_dasd(disk):
                log.debug("Found unformatted DASD: %s", self.get_dasd_info(disk))
                result.append(disk)

        return result

    def _get_ldl_dasds(self, disks):
        """Returns a list of LDL DASDs."""
        result = []

        if not self._can_format_ldl:
            log.debug("We are not allowed to format LDL DASDs.")
            return result

        for disk in disks:
            if self._is_ldl_dasd(disk):
                log.debug("Found LDL DASD: %s", self.get_dasd_info(disk))
                result.append(disk)

        return result

    def update_restrictions(self, data):
        """Read kickstart data to update the restrictions."""
        self._can_format_unformatted = data.zerombr.zerombr
        self._can_format_ldl = data.clearpart.cdl

    def search_disks(self, disks):
        """Search for a list of disks for DASDs to format."""
        self._dasds = list(set(self._get_unformatted_dasds(disks) + self._get_ldl_dasds(disks)))

    def should_run(self):
        """Should we run the formatting?"""
        return bool(self._dasds)

    def do_format(self, disk):
        """Format a disk."""
        try:
            self.report.emit(_("Formatting %s") % self.get_dasd_info(disk))
            blockdev.s390.dasd_format(disk.name)
        except blockdev.S390Error as err:
            self.report.emit(_("Failed formatting %s") % self.get_dasd_info(disk))
            log.error(err)

    def run(self, storage, data):
        """Format all found DASDs and update the storage.

        This method could be run in a separate thread.
        """
        # Check if we have something to format.
        if not self._dasds:
            self.report.emit(_("Nothing to format"))
            return

        # Format all found DASDs.
        self.report.emit(_("Formatting DASDs"))
        for disk in self._dasds:
            self.do_format(disk)

        # Update the storage.
        self.report.emit(_("Probing storage"))
        storage_initialize(storage, data, storage.devicetree.protected_dev_names)

        # Update also the storage snapshot to reflect the changes.
        if on_disk_storage.created:
            on_disk_storage.dispose_snapshot()
        on_disk_storage.create_snapshot(storage)

    @staticmethod
    def run_automatically(storage, data, callback=None):
        """Run the DASD formatting automatically.

        This method could be run in a separate thread.
        """
        if not flags.automatedInstall:
            return

        if not DasdFormatting.is_supported():
            return

        disks = getDisks(storage.devicetree)

        formatting = DasdFormatting()
        formatting.update_restrictions(data)
        formatting.search_disks(disks)

        if not formatting.should_run():
            return

        if callback:
            formatting.report.connect(callback)

        formatting.run(storage, data)

        if callback:
            formatting.report.disconnect(callback)
