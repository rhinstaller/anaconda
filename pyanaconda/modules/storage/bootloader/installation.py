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
from pyanaconda.modules.storage.constants import BootloaderMode

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.bootloader.installation import configure_boot_loader, install_boot_loader
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.modules.common.task import Task

log = get_module_logger(__name__)


__all__ = ["ConfigureBootloaderTask", "InstallBootloaderTask"]


class ConfigureBootloaderTask(Task):
    """Installation task for the bootloader configuration."""

    def __init__(self, storage, mode, kernel_versions, sysroot):
        """Create a new task."""
        super().__init__()
        self._storage = storage
        self._mode = mode
        self._versions = kernel_versions
        self._sysroot = sysroot

    @property
    def name(self):
        return "Configure the bootloader"

    def run(self):
        """Run the task."""
        if conf.target.is_directory:
            log.debug("The bootloader configuration is disabled for dir installations.")
            return

        if self._mode == BootloaderMode.DISABLED:
            log.debug("The bootloader configuration is disabled.")
            return

        configure_boot_loader(
            sysroot=self._sysroot,
            storage=self._storage,
            kernel_versions=self._versions
        )


class InstallBootloaderTask(Task):
    """Installation task for the bootloader."""

    def __init__(self, storage, mode, sysroot):
        """Create a new task."""
        super().__init__()
        self._storage = storage
        self._mode = mode
        self._sysroot = sysroot

    @property
    def name(self):
        return "Install the bootloader"

    def run(self):
        """Run the task."""
        if conf.target.is_directory:
            log.debug("The bootloader installation is disabled for dir installations.")
            return

        if self._mode == BootloaderMode.DISABLED:
            log.debug("The bootloader installation is disabled.")
            return

        if self._mode == BootloaderMode.SKIPPED:
            log.debug("The bootloader installation is skipped.")
            return

        install_boot_loader(storage=self._storage)
