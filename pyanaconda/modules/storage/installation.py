#
# Installation tasks
#
# Copyright (C) 2019 Red Hat, Inc.
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
from pyanaconda.bootloader.installation import configure_boot_loader, install_boot_loader
from pyanaconda.modules.common.task import Task
from pyanaconda.storage.installation import turn_on_filesystems, write_storage_configuration

__all__ = ["ActivateFilesystemsTask", "MountFilesystemsTask", "WriteConfigurationTask"]


class ActivateFilesystemsTask(Task):
    """Installation task for activation of the storage configuration."""

    def __init__(self, storage):
        """Create a new task."""
        super().__init__()
        self._storage = storage

    @property
    def name(self):
        return "Activate filesystems"

    def run(self):
        """Do the activation."""
        turn_on_filesystems(self._storage)


class MountFilesystemsTask(Task):
    """Installation task for mounting the filesystems."""

    def __init__(self, storage):
        """Create a new task."""
        super().__init__()
        self._storage = storage

    @property
    def name(self):
        return "Mount filesystems"

    def run(self):
        """Mount the filesystems."""
        self._storage.mount_filesystems()


class WriteConfigurationTask(Task):
    """Installation task for writing out the storage configuration."""

    def __init__(self, storage, sysroot):
        """Create a new task."""
        super().__init__()
        self._storage = storage
        self._sysroot = sysroot

    @property
    def name(self):
        return "Write the storage configuration"

    def run(self):
        """Mount the filesystems."""
        write_storage_configuration(self._storage, sysroot=self._sysroot)


class ConfigureBootloaderTask(Task):
    """Installation task for the boot loader configuration."""

    def __init__(self, storage, kernel_versions, sysroot):
        """Create a new task."""
        super().__init__()
        self._storage = storage
        self._versions = kernel_versions
        self._sysroot = sysroot

    @property
    def name(self):
        return "Configure the boot loader"

    def run(self):
        """Run the task."""
        configure_boot_loader(
            sysroot=self._sysroot,
            storage=self._storage,
            kernel_versions=self._versions
        )


class InstallBootloaderTask(Task):
    """Installation task for the boot loader."""

    def __init__(self, storage):
        """Create a new task."""
        super().__init__()
        self._storage = storage

    @property
    def name(self):
        return "Install the boot loader"

    def run(self):
        """Run the task."""
        install_boot_loader(storage=self._storage)
