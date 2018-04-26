#
# Kickstart module for the storage.
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
from pyanaconda.dbus import DBus
from pyanaconda.modules.common.base import KickstartModule
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.modules.storage.bootloader import BootloaderModule
from pyanaconda.modules.storage.disk_initialization import DiskInitializationModule
from pyanaconda.modules.storage.disk_selection import DiskSelectionModule
from pyanaconda.modules.storage.kickstart import StorageKickstartSpecification
from pyanaconda.modules.storage.partitioning import AutoPartitioningModule
from pyanaconda.modules.storage.storage_interface import StorageInterface

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class StorageModule(KickstartModule):
    """The Storage module."""

    def __init__(self):
        super().__init__()
        self._modules = []

        self._disk_init_module = DiskInitializationModule()
        self._add_module(self._disk_init_module)

        self._disk_selection_module = DiskSelectionModule()
        self._add_module(self._disk_selection_module)

        self._bootloader_module = BootloaderModule()
        self._add_module(self._bootloader_module)

        self._autopart_module = AutoPartitioningModule()
        self._add_module(self._autopart_module)

    def _add_module(self, storage_module):
        """Add a base kickstart module."""
        self._modules.append(storage_module)

    def publish(self):
        """Publish the module."""
        for kickstart_module in self._modules:
            kickstart_module.publish()

        DBus.publish_object(STORAGE.object_path, StorageInterface(self))
        DBus.register_service(STORAGE.service_name)

    @property
    def kickstart_specification(self):
        """Return the kickstart specification."""
        return StorageKickstartSpecification

    def process_kickstart(self, data):
        """Process the kickstart data."""
        log.debug("Processing kickstart data...")

        for kickstart_module in self._modules:
            kickstart_module.process_kickstart(data)

    def generate_temporary_kickstart(self):
        """Return the temporary kickstart string."""
        return self.generate_kickstart(skip_unsupported=True)

    def generate_kickstart(self, skip_unsupported=False):  # pylint: disable=arguments-differ
        """Return the kickstart string."""
        log.debug("Generating kickstart data...")
        data = self.get_kickstart_handler()

        for kickstart_module in self._modules:

            # The auto partitioning module is not used in UI for now.
            if skip_unsupported and isinstance(kickstart_module, AutoPartitioningModule):
                continue

            kickstart_module.setup_kickstart(data)

        return str(data)
