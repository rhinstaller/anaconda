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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from blivet import __version__ as blivet_version

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.dbus import DBus
from pyanaconda.core.signal import Signal
from pyanaconda.modules.common.base import KickstartService
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.modules.common.containers import TaskContainer
from pyanaconda.modules.common.errors.storage import InvalidStorageError
from pyanaconda.modules.common.structures.requirement import Requirement
from pyanaconda.modules.common.submodule_manager import SubmoduleManager
from pyanaconda.modules.storage.bootloader import BootloaderModule
from pyanaconda.modules.storage.checker import StorageCheckerModule
from pyanaconda.modules.storage.dasd import DASDModule
from pyanaconda.modules.storage.devicetree import DeviceTreeModule, create_storage
from pyanaconda.modules.storage.disk_initialization import DiskInitializationModule
from pyanaconda.modules.storage.disk_selection import DiskSelectionModule
from pyanaconda.modules.storage.fcoe import FCOEModule
from pyanaconda.modules.storage.installation import (
    CreateStorageLayoutTask,
    MountFilesystemsTask,
    WriteConfigurationTask,
)
from pyanaconda.modules.storage.iscsi import ISCSIModule
from pyanaconda.modules.storage.kickstart import StorageKickstartSpecification
from pyanaconda.modules.storage.nvme import NVMEModule
from pyanaconda.modules.storage.partitioning.constants import PartitioningMethod
from pyanaconda.modules.storage.partitioning.factory import PartitioningFactory
from pyanaconda.modules.storage.partitioning.validate import StorageValidateTask
from pyanaconda.modules.storage.platform import platform
from pyanaconda.modules.storage.reset import ScanDevicesTask
from pyanaconda.modules.storage.snapshot import SnapshotModule
from pyanaconda.modules.storage.storage_interface import StorageInterface
from pyanaconda.modules.storage.storage_subscriber import StorageSubscriberModule
from pyanaconda.modules.storage.teardown import (
    TeardownDiskImagesTask,
    UnmountFilesystemsTask,
)
from pyanaconda.modules.storage.zfcp import ZFCPModule

log = get_module_logger(__name__)


class StorageService(KickstartService):
    """The Storage service."""

    def __init__(self):
        super().__init__()
        # The storage model.
        self._current_storage = None
        self._storage_playground = None
        self.storage_changed = Signal()

        # The created partitioning modules.
        self._created_partitioning = []
        self.created_partitioning_changed = Signal()

        # The applied partitioning module.
        self._applied_partitioning = None
        self.applied_partitioning_changed = Signal()
        self.partitioning_reset = Signal()

        # Initialize modules.
        self._modules = SubmoduleManager()

        self._storage_checker_module = StorageCheckerModule()
        self._modules.add_module(self._storage_checker_module)

        self._device_tree_module = DeviceTreeModule()
        self._modules.add_module(self._device_tree_module)

        self._disk_init_module = DiskInitializationModule()
        self._modules.add_module(self._disk_init_module)

        self._disk_selection_module = DiskSelectionModule()
        self._modules.add_module(self._disk_selection_module)

        self._snapshot_module = SnapshotModule()
        self._modules.add_module(self._snapshot_module)

        self._bootloader_module = BootloaderModule()
        self._modules.add_module(self._bootloader_module)

        self._fcoe_module = FCOEModule()
        self._modules.add_module(self._fcoe_module)

        self._iscsi_module = ISCSIModule()
        self._modules.add_module(self._iscsi_module)

        self._nvme_module = NVMEModule()
        self._modules.add_module(self._nvme_module)

        self._dasd_module = DASDModule()
        self._modules.add_module(self._dasd_module)

        self._zfcp_module = ZFCPModule()
        self._modules.add_module(self._zfcp_module)

        # Connect modules to signals.
        for module in self._modules:
            if isinstance(module, StorageSubscriberModule):
                self.storage_changed.connect(module.on_storage_changed)

        self._disk_init_module.format_unrecognized_enabled_changed.connect(
            self._dasd_module.on_format_unrecognized_enabled_changed
        )
        self._disk_init_module.format_ldl_enabled_changed.connect(
            self._dasd_module.on_format_ldl_enabled_changed
        )
        self._disk_selection_module.protected_devices_changed.connect(
            self.on_protected_devices_changed
        )

        # After connecting modules to signals, create the initial
        # storage model. It will be propagated to all modules.
        self._set_storage(create_storage())

    def publish(self):
        """Publish the module."""
        TaskContainer.set_namespace(STORAGE.namespace)

        self._modules.publish_modules()

        DBus.publish_object(STORAGE.object_path, StorageInterface(self))
        DBus.register_service(STORAGE.service_name)

    @property
    def kickstart_specification(self):
        """Return the kickstart specification."""
        return StorageKickstartSpecification

    def process_kickstart(self, data):
        """Process the kickstart data."""
        # Process the kickstart data in modules.
        self._modules.process_kickstart(data)

        # Set the default filesystem type.
        if data.autopart.autopart and data.autopart.fstype:
            self.storage.set_default_fstype(data.autopart.fstype)

        # Create a new partitioning module.
        partitioning_method = PartitioningFactory.get_method_for_kickstart(data)

        if partitioning_method:
            partitioning_module = self.create_partitioning(partitioning_method)
            partitioning_module.process_kickstart(data)

    def setup_kickstart(self, data):
        """Set up the kickstart data."""
        self._modules.setup_kickstart(data)

        if self.applied_partitioning:
            self.applied_partitioning.setup_kickstart(data)

    def generate_kickstart(self):
        """Generate kickstart string representation of this module's data

        Adds Blivet version to the output because most of the strings come from Blivet anyway.
        """
        return "# Generated using Blivet version {}\n{}".format(
            blivet_version,
            super().generate_kickstart()
        )

    @property
    def storage(self):
        """The storage model.

        :return: an instance of Blivet
        """
        if self._storage_playground:
            return self._storage_playground

        if not self._current_storage:
            self._set_storage(create_storage())

        return self._current_storage

    def _set_storage(self, storage):
        """Set the current storage model.

        The current storage is the latest model of
        the system's storage configuration created
        by scanning all devices.

        :param storage: a storage
        """
        self._current_storage = storage

        if self._storage_playground:
            return

        self.storage_changed.emit(storage)
        log.debug("The storage model has changed.")

    def _set_storage_playground(self, storage):
        """Set the storage playground.

        The storage playground is a model of a valid
        partitioned storage configuration, that can be
        used for an installation.

        :param storage: a storage or None
        """
        self._storage_playground = storage

        if storage is None:
            storage = self.storage

        self.storage_changed.emit(storage)
        log.debug("The storage model has changed.")

    def on_protected_devices_changed(self, protected_devices):
        """Update the protected devices in the storage model."""
        if not self._current_storage:
            return

        self.storage.protect_devices(protected_devices)

    def scan_devices_with_task(self):
        """Scan all devices with a task.

        We will reset a copy of the current storage model
        and switch the models if the reset is successful.

        :return: a task
        """
        # Copy the storage.
        storage = self.storage.copy()

        # Set up the storage.
        storage.ignored_disks = self._disk_selection_module.ignored_disks
        storage.exclusive_disks = self._disk_selection_module.exclusive_disks
        storage.protected_devices = self._disk_selection_module.protected_devices
        storage.disk_images = self._disk_selection_module.disk_images

        # Create the task.
        task = ScanDevicesTask(storage)
        task.succeeded_signal.connect(lambda: self._set_storage(storage))
        return task

    def create_partitioning(self, method: PartitioningMethod):
        """Create a new partitioning.

        Allowed values:
            AUTOMATIC
            CUSTOM
            MANUAL
            INTERACTIVE
            BLIVET

        :param PartitioningMethod method: a partitioning method
        :return: a partitioning module
        """
        module = PartitioningFactory.create_partitioning(method)

        # Update the module.
        module.on_storage_changed(
            self._current_storage
        )
        module.on_selected_disks_changed(
            self._disk_selection_module.selected_disks
        )

        # Connect the callbacks to signals.
        self.storage_changed.connect(
            module.on_storage_changed
        )
        self.partitioning_reset.connect(
            module.on_partitioning_reset
        )
        self._disk_selection_module.selected_disks_changed.connect(
            module.on_selected_disks_changed
        )

        # Update the list of modules.
        self._add_created_partitioning(module)
        return module

    @property
    def created_partitioning(self):
        """List of all created partitioning modules."""
        return self._created_partitioning

    def _add_created_partitioning(self, module):
        """Add a created partitioning module."""
        self._created_partitioning.append(module)
        self.created_partitioning_changed.emit(module)
        log.debug("Created the partitioning %s.", module)

    def apply_partitioning(self, module):
        """Apply a partitioning.

        :param module: a partitioning module
        :raise: InvalidStorageError if the partitioning is not valid
        """
        # Validate the partitioning.
        storage = module.storage.copy()
        task = StorageValidateTask(storage)
        report = task.run()

        if not report.is_valid():
            raise InvalidStorageError(" ".join(report.error_messages))

        # Apply the partitioning.
        self._set_storage_playground(storage)
        self._set_applied_partitioning(module)

    @property
    def applied_partitioning(self):
        """The applied partitioning."""
        return self._applied_partitioning

    def _set_applied_partitioning(self, module):
        """Set the applied partitioning.

        :param module: a partitioning module or None
        """
        self._applied_partitioning = module
        self.applied_partitioning_changed.emit()

        if module is None:
            module = "NONE"

        log.debug("The partitioning %s is applied.", module)

    def reset_partitioning(self):
        """Reset the partitioning."""
        self._set_storage_playground(None)
        self._set_applied_partitioning(None)
        self.partitioning_reset.emit()

    def collect_requirements(self):
        """Return installation requirements for this module.

        :return: a list of requirements
        """
        requirements = []

        # Add the platform requirements.
        for name in platform.packages:
            requirements.append(Requirement.for_package(
                name, reason="Required for the platform."
            ))

        # Add the storage requirements.
        for name in self.storage.packages:
            requirements.append(Requirement.for_package(
                name, reason="Required to manage storage devices."
            ))

        # Add other requirements, for example for bootloader.
        requirements.extend(self._modules.collect_requirements())

        return requirements

    def install_with_tasks(self):
        """Returns installation tasks of this module.

        :returns: list of installation tasks
        """
        storage = self.storage

        return [
            CreateStorageLayoutTask(storage),
            MountFilesystemsTask(storage)
        ]

    def write_configuration_with_task(self):
        """Write the storage configuration with a task.

        FIXME: This is a temporary workaround.

        :return: an installation task
        """
        return WriteConfigurationTask(self.storage)

    def teardown_with_tasks(self):
        """Returns teardown tasks for this module.

        :return: a list installation tasks
        """
        storage = self.storage

        return [
            UnmountFilesystemsTask(storage),
            TeardownDiskImagesTask(storage)
        ]
