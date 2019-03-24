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
from blivet import arch
from blivet.size import Size

from pyanaconda.core.signal import Signal
from pyanaconda.dbus import DBus
from pyanaconda.modules.common.base import KickstartModule
from pyanaconda.modules.common.constants.objects import AUTO_PARTITIONING, MANUAL_PARTITIONING, \
    CUSTOM_PARTITIONING, BLIVET_PARTITIONING
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.modules.storage.bootloader import BootloaderModule
from pyanaconda.modules.storage.dasd import DASDModule
from pyanaconda.modules.storage.devicetree import DeviceTreeHandler
from pyanaconda.modules.storage.disk_initialization import DiskInitializationModule
from pyanaconda.modules.storage.disk_selection import DiskSelectionModule
from pyanaconda.modules.storage.fcoe import FCOEModule
from pyanaconda.modules.storage.installation import MountFilesystemsTask, ActivateFilesystemsTask, \
    WriteConfigurationTask
from pyanaconda.modules.storage.kickstart import StorageKickstartSpecification
from pyanaconda.modules.storage.nvdimm import NVDIMMModule
from pyanaconda.modules.storage.partitioning import AutoPartitioningModule, \
    ManualPartitioningModule, CustomPartitioningModule, BlivetPartitioningModule
from pyanaconda.modules.storage.partitioning.validate import StorageValidateTask
from pyanaconda.modules.storage.reset import StorageResetTask
from pyanaconda.modules.storage.snapshot import SnapshotModule
from pyanaconda.modules.storage.storage_interface import StorageInterface
from pyanaconda.modules.storage.zfcp import ZFCPModule
from pyanaconda.storage.initialization import enable_installer_mode, create_storage
from pyanaconda.storage.utils import get_required_device_size

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class StorageModule(KickstartModule, DeviceTreeHandler):
    """The Storage module."""

    def __init__(self):
        super().__init__()
        # Initialize Blivet.
        enable_installer_mode()

        # The storage model.
        self._storage = None
        self.storage_changed = Signal()

        # Initialize modules.
        self._modules = []

        self._disk_init_module = DiskInitializationModule()
        self._add_module(self._disk_init_module)

        self._disk_selection_module = DiskSelectionModule()
        self._add_module(self._disk_selection_module)

        self._snapshot_module = SnapshotModule()
        self._add_module(self._snapshot_module)

        self._bootloader_module = BootloaderModule()
        self._add_module(self._bootloader_module)

        self._fcoe_module = FCOEModule()
        self._add_module(self._fcoe_module)

        self._nvdimm_module = NVDIMMModule()
        self._add_module(self._nvdimm_module)

        self._dasd_module = None
        self._zfcp_module = None

        if arch.is_s390():
            self._dasd_module = DASDModule()
            self._add_module(self._dasd_module)

            self._zfcp_module = ZFCPModule()
            self._add_module(self._zfcp_module)

        # Initialize the partitioning modules.
        self._partitioning_modules = {}

        self._auto_part_module = AutoPartitioningModule()
        self._add_partitioning_module(AUTO_PARTITIONING.object_path, self._auto_part_module)

        self._manual_part_module = ManualPartitioningModule()
        self._add_partitioning_module(MANUAL_PARTITIONING.object_path, self._manual_part_module)

        self._custom_part_module = CustomPartitioningModule()
        self._add_partitioning_module(CUSTOM_PARTITIONING.object_path, self._custom_part_module)

        self._blivet_part_module = BlivetPartitioningModule()
        self._add_partitioning_module(BLIVET_PARTITIONING.object_path, self._blivet_part_module)

        # Connect modules to signals.
        self.storage_changed.connect(self._snapshot_module.on_storage_reset)
        self.storage_changed.connect(self._disk_init_module.on_storage_reset)

    def _add_module(self, storage_module):
        """Add a base kickstart module."""
        self._modules.append(storage_module)

    def _add_partitioning_module(self, object_path, partitioning_module):
        """Add a partitioning module."""
        # Add the module.
        self._modules.append(partitioning_module)
        self._partitioning_modules[object_path] = partitioning_module

        # Connect the callbacks.
        self.storage_changed.connect(partitioning_module.on_storage_reset)

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

        # Process the kickstart data in modules.
        for kickstart_module in self._modules:
            kickstart_module.process_kickstart(data)

        # Set the default filesystem type.
        if data.autopart.autopart and data.autopart.fstype:
            self.storage.set_default_fstype(data.autopart.fstype)
            self.storage.set_default_boot_fstype(data.autopart.fstype)

    def generate_kickstart(self):
        """Return the kickstart string."""
        log.debug("Generating kickstart data...")
        data = self.get_kickstart_handler()

        for kickstart_module in self._modules:
            kickstart_module.setup_kickstart(data)

        return str(data)

    @property
    def storage(self):
        """The storage model.

        :return: an instance of Blivet
        """
        if not self._storage:
            self.set_storage(create_storage())

        return self._storage

    def set_storage(self, storage):
        """Set the storage model."""
        self._storage = storage
        self.storage_changed.emit(storage)
        log.debug("The storage model has changed.")

    def reset_with_task(self):
        """Reset the storage model.

        We will reset a copy of the current storage model
        and switch the models if the reset is successful.

        :return: a DBus path to a task
        """
        # Copy the storage.
        storage = self.storage.copy()

        # Set up the storage.
        storage.ignored_disks = self._disk_selection_module.ignored_disks
        storage.exclusive_disks = self._disk_selection_module.exclusive_disks
        storage.protected_devices = self._disk_selection_module.protected_devices

        # Create the task.
        task = StorageResetTask(storage)
        # FIXME: Don't set the storage if the task has failed.
        task.stopped_signal.connect(lambda: self.set_storage(storage))

        # Publish the task.
        path = self.publish_task(STORAGE.namespace, task)
        return path

    def get_required_device_size(self, required_space):
        """Get device size we need to get the required space on the device.

        :param int required_space: a required space in bytes
        :return int: a required device size in bytes
        """
        return get_required_device_size(Size(required_space)).get_bytes()

    def apply_partitioning(self, object_path):
        """Apply a partitioning.

        :param object_path: an object path of a partitioning module
        :raise: InvalidStorageError of the partitioning is not valid
        """
        # Get the partitioning module.
        module = self._partitioning_modules.get(object_path)

        if not module:
            raise ValueError("Unknown partitioning {}.".format(object_path))

        # Validate the partitioning.
        storage = module.storage
        task = StorageValidateTask(storage)
        task.run()

        # Apply the partitioning.
        self.set_storage(storage.copy())
        log.debug("Applied the partitioning from %s.", object_path)

    def install_with_tasks(self, sysroot):
        """Returns installation tasks of this module.

        FIXME: This is a simplified version of the storage installation.

        :param sysroot: a path to the root of the installed system
        :returns: list of object paths of installation tasks.
        """
        storage = self.storage

        tasks = [
            ActivateFilesystemsTask(storage),
            MountFilesystemsTask(storage),
            WriteConfigurationTask(storage, sysroot)
        ]

        paths = [
            self.publish_task(STORAGE.namespace, task) for task in tasks
        ]

        return paths
