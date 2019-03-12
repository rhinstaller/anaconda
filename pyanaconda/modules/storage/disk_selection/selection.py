#
# Disk selection module.
#
# Copyright (C) 2018 Red Hat, Inc.
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
from pyanaconda.core.signal import Signal
from pyanaconda.dbus import DBus
from pyanaconda.modules.common.base import KickstartBaseModule
from pyanaconda.modules.common.constants.objects import DISK_SELECTION
from pyanaconda.modules.storage.disk_selection.selection_interface import DiskSelectionInterface

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class DiskSelectionModule(KickstartBaseModule):
    """The disk selection module."""

    def __init__(self):
        super().__init__()
        self.selected_disks_changed = Signal()
        self._selected_disks = []

        self.exclusive_disks_changed = Signal()
        self._exclusive_disks = []

        self.ignored_disks_changed = Signal()
        self._ignored_disks = []

        self.protected_devices_changed = Signal()
        self._protected_devices = []

    def publish(self):
        """Publish the module."""
        DBus.publish_object(DISK_SELECTION.object_path, DiskSelectionInterface(self))

    def process_kickstart(self, data):
        """Process the kickstart data."""
        self.set_selected_disks(data.ignoredisk.onlyuse)
        self.set_exclusive_disks(data.ignoredisk.onlyuse)
        self.set_ignored_disks(data.ignoredisk.ignoredisk)

    def setup_kickstart(self, data):
        """Setup the kickstart data."""
        data.ignoredisk.onlyuse = self.selected_disks
        data.ignoredisk.ignoredisk = self.ignored_disks
        return data

    @property
    def selected_disks(self):
        """The list of drives to use."""
        return self._selected_disks

    def set_selected_disks(self, drives):
        """Set the list of selected disks

        Specifies those disks that anaconda can use for
        partitioning, formatting, and clearing.

        :param drives: a list of drives names
        """
        self._selected_disks = drives
        self.selected_disks_changed.emit()
        log.debug("Selected disks are set to '%s'.", drives)

    @property
    def exclusive_disks(self):
        """The list of drives to scan."""
        return self._exclusive_disks

    def set_exclusive_disks(self, drives):
        """Set the list of drives to scan.

        Specifies those disks that anaconda will scan during
        the storage reset. If the list is empty, anaconda will
        scan all drives.

        It can be set from the kickstart with 'ignoredisk --onlyuse'.

        :param drives: a list of drives names
        """
        self._exclusive_disks = drives
        self.exclusive_disks_changed.emit()
        log.debug("Exclusive disks are set to '%s'.", drives)

    @property
    def ignored_disks(self):
        """The list of drives to ignore."""
        return self._ignored_disks

    def set_ignored_disks(self, drives):
        """Set the list of ignored disks.

        Specifies those disks that anaconda should not touch
        when it does partitioning, formatting, and clearing.

        :param drives: a list of drive names
        """
        self._ignored_disks = drives
        self.ignored_disks_changed.emit()
        log.debug("Ignored disks are set to '%s'.", drives)

    @property
    def protected_devices(self):
        """The list of devices to protect."""
        return self._protected_devices

    def set_protected_devices(self, devices):
        """Set the list of protected devices.

        Specifies those disks that anaconda should protect.

        :param devices: a list of device names
        """
        self._protected_devices = devices
        self.protected_devices_changed.emit()
        log.debug("Protected devices are set to '%s'.", devices)
