#
# Auto partitioning module.
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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import copy

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.signal import Signal
from pyanaconda.modules.common.structures.partitioning import PartitioningRequest
from pyanaconda.modules.storage.partitioning.automatic.automatic_interface import (
    AutoPartitioningInterface,
)
from pyanaconda.modules.storage.partitioning.automatic.automatic_partitioning import (
    AutomaticPartitioningTask,
)
from pyanaconda.modules.storage.partitioning.automatic.resizable_module import (
    ResizableDeviceTreeModule,
)
from pyanaconda.modules.storage.partitioning.base import PartitioningModule
from pyanaconda.modules.storage.partitioning.constants import PartitioningMethod

log = get_module_logger(__name__)


class AutoPartitioningModule(PartitioningModule):
    """The auto partitioning module."""

    def __init__(self):
        """Initialize the module."""
        super().__init__()
        self.request_changed = Signal()
        self._request = PartitioningRequest()

    @property
    def partitioning_method(self):
        """Type of the partitioning method."""
        return PartitioningMethod.AUTOMATIC

    def for_publication(self):
        """Return a DBus representation."""
        return AutoPartitioningInterface(self)

    def _create_device_tree(self):
        """Create the device tree module."""
        return ResizableDeviceTreeModule()

    def process_kickstart(self, data):
        """Process the kickstart data."""
        request = PartitioningRequest()

        if data.autopart.type is not None:
            request.partitioning_scheme = data.autopart.type

        if data.autopart.fstype:
            request.file_system_type = data.autopart.fstype

        if data.autopart.noboot:
            request.excluded_mount_points.append("/boot")

        if data.autopart.nohome:
            request.excluded_mount_points.append("/home")

        if data.autopart.noswap:
            request.excluded_mount_points.append("swap")

        request.hibernation = data.autopart.hibernation

        if data.autopart.encrypted:
            request.encrypted = True
            request.passphrase = data.autopart.passphrase
            request.cipher = data.autopart.cipher
            request.luks_version = data.autopart.luks_version

            request.pbkdf = data.autopart.pbkdf
            request.pbkdf_memory = data.autopart.pbkdf_memory
            request.pbkdf_time = data.autopart.pbkdf_time
            request.pbkdf_iterations = data.autopart.pbkdf_iterations

            request.escrow_certificate = data.autopart.escrowcert
            request.backup_passphrase_enabled = data.autopart.backuppassphrase

            request.opal_admin_passphrase = data.autopart.hw_passphrase

        self.set_request(request)

    def setup_kickstart(self, data):
        """Setup the kickstart data."""
        data.autopart.autopart = True
        data.autopart.fstype = self.request.file_system_type

        if self.request.partitioning_scheme != conf.storage.default_scheme:
            data.autopart.type = self.request.partitioning_scheme

        data.autopart.nohome = "/home" in self.request.excluded_mount_points
        data.autopart.noboot = "/boot" in self.request.excluded_mount_points
        data.autopart.noswap = "swap" in self.request.excluded_mount_points

        data.autopart.hibernation = self.request.hibernation

        data.autopart.encrypted = self.request.encrypted

        # Don't generate sensitive information.
        data.autopart.passphrase = ""
        data.autopart.cipher = self.request.cipher
        data.autopart.luks_version = self.request.luks_version

        data.autopart.pbkdf = self.request.pbkdf
        data.autopart.pbkdf_memory = self.request.pbkdf_memory
        data.autopart.pbkdf_time = self.request.pbkdf_time
        data.autopart.pbkdf_iterations = self.request.pbkdf_iterations

        data.autopart.escrowcert = self.request.escrow_certificate
        data.autopart.backuppassphrase = self.request.backup_passphrase_enabled

        # Don't generate sensitive information.
        data.autopart.hw_passphrase = ""

    @property
    def request(self):
        """The partitioning request."""
        return self._request

    def set_request(self, request):
        """Set the partitioning request.

        :param request: a request
        """
        self._request = request
        self.request_changed.emit()
        log.debug("Request is set to '%s'.", request)

    def requires_passphrase(self):
        """Is the default passphrase required?

        :return: True or False
        """
        return self.request.encrypted and not self.request.passphrase

    def set_passphrase(self, passphrase):
        """Set a default passphrase for all encrypted devices.

        :param passphrase: a string with a passphrase
        """
        # Update the request with a new copy.
        request = copy.deepcopy(self.request)
        request.passphrase = passphrase
        self.set_request(request)

    def configure_with_task(self):
        """Schedule the partitioning actions."""
        return AutomaticPartitioningTask(self.storage, self.request)
