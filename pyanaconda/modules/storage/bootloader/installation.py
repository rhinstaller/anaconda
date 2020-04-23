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
from blivet import arch
from blivet.devices import BTRFSDevice
from pyanaconda.modules.storage.bootloader import BootLoaderError

from pyanaconda.core.util import execInSysroot
from pyanaconda.modules.common.errors.installation import BootloaderInstallationError
from pyanaconda.modules.storage.constants import BootloaderMode

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.modules.storage.bootloader.utils import configure_boot_loader, install_boot_loader
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.modules.common.task import Task

log = get_module_logger(__name__)


__all__ = ["ConfigureBootloaderTask", "InstallBootloaderTask", "FixBTRFSBootloaderTask",
           "FixZIPLBootloaderTask"]


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

    def __init__(self, storage, mode):
        """Create a new task."""
        super().__init__()
        self._storage = storage
        self._mode = mode

    @property
    def name(self):
        return "Install the bootloader"

    def run(self):
        """Run the task.

        :raise: BootloaderInstallationError if the installation fails
        """
        if conf.target.is_directory:
            log.debug("The bootloader installation is disabled for dir installations.")
            return

        if self._mode == BootloaderMode.DISABLED:
            log.debug("The bootloader installation is disabled.")
            return

        if self._mode == BootloaderMode.SKIPPED:
            log.debug("The bootloader installation is skipped.")
            return

        try:
            install_boot_loader(storage=self._storage)
        except BootLoaderError as e:
            log.error("Bootloader installation has failed: %s", e)
            raise BootloaderInstallationError(str(e)) from None


class FixBTRFSBootloaderTask(Task):
    """Installation task fixing the bootloader on BTRFS.

    This works around 2 problems, /boot on BTRFS and BTRFS installations
    where the initrd is recreated after the first writeBootLoader call.
    This reruns it after the new initrd has been created, fixing the
    kernel root and subvol args and adding the missing initrd entry.
    """

    def __init__(self, storage, mode, kernel_versions, sysroot):
        """Create a new task."""
        super().__init__()
        self._storage = storage
        self._mode = mode
        self._versions = kernel_versions
        self._sysroot = sysroot

    @property
    def name(self):
        return "Fix the bootloader on BTRFS"

    def run(self):
        """Run the task."""
        if conf.target.is_directory:
            log.debug("The bootloader installation is disabled for dir installations.")
            return

        if self._mode == BootloaderMode.DISABLED:
            log.debug("The bootloader installation is disabled.")
            return

        if not isinstance(self._storage.mountpoints.get("/"), BTRFSDevice):
            log.debug("The bootloader is not on BTRFS.")
            return

        ConfigureBootloaderTask(
            self._storage,
            self._mode,
            self._versions,
            self._sysroot
        ).run()

        InstallBootloaderTask(
            self._storage,
            self._mode
        ).run()


class FixZIPLBootloaderTask(Task):
    """Installation task fixing the ZIPL bootloader.

    Invoking zipl should be the last thing done on a s390x installation (see #1652727).
    """

    def __init__(self, mode):
        """Create a new task."""
        super().__init__()
        self._mode = mode

    @property
    def name(self):
        return "Rerun zipl"

    def run(self):
        """Run the task."""
        if not arch.is_s390():
            log.debug("ZIPL can be run only on s390x.")
            return

        if conf.target.is_directory:
            log.debug("The bootloader installation is disabled for dir installations.")
            return

        if self._mode == BootloaderMode.DISABLED:
            log.debug("The bootloader installation is disabled.")
            return

        execInSysroot("zipl", [])
