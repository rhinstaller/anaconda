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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from blivet import arch
from blivet.devices import BTRFSDevice

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import PAYLOAD_LIVE_TYPES, PAYLOAD_TYPE_RPM_OSTREE
from pyanaconda.core.util import execWithRedirect
from pyanaconda.modules.common.errors.installation import BootloaderInstallationError
from pyanaconda.modules.common.task import Task
from pyanaconda.modules.payloads.payload.rpm_ostree.util import have_bootupd
from pyanaconda.modules.storage.bootloader import BootLoaderError
from pyanaconda.modules.storage.bootloader.systemd import SystemdBoot
from pyanaconda.modules.storage.bootloader.utils import (
    configure_boot_loader,
    create_bls_entries,
    create_rescue_images,
    recreate_initrds,
)
from pyanaconda.modules.storage.constants import BootloaderMode

log = get_module_logger(__name__)


__all__ = [
    "CollectKernelArgumentsTask",
    "ConfigureBootloaderTask",
    "CreateBLSEntriesTask",
    "CreateRescueImagesTask",
    "FixBTRFSBootloaderTask",
    "FixZIPLBootloaderTask",
    "InstallBootloaderTask",
    "RecreateInitrdsTask",
]


class CreateRescueImagesTask(Task):
    """Installation task that creates rescue images."""

    def __init__(self, payload_type, kernel_versions, sysroot):
        """Create a new task."""
        super().__init__()
        self._payload_type = payload_type
        self._versions = kernel_versions
        self._sysroot = sysroot

    @property
    def name(self):
        return "Create rescue images"

    def run(self):
        """Run the task."""
        #  Live payloads need to create rescue images
        #  before the bootloader is written on the system.
        if self._payload_type not in PAYLOAD_LIVE_TYPES:
            log.debug("Only live payloads require this fix.")
            return

        create_rescue_images(
            sysroot=self._sysroot,
            kernel_versions=self._versions
        )


class ConfigureBootloaderTask(Task):
    """Installation task for the bootloader configuration."""

    def __init__(self, storage, mode, payload_type, kernel_versions, sysroot):
        """Create a new task."""
        super().__init__()
        self._storage = storage
        self._mode = mode
        self._payload_type = payload_type
        self._versions = kernel_versions
        self._sysroot = sysroot

    @property
    def name(self):
        return "Configure the bootloader"

    def run(self):
        """Run the task."""
        if self._payload_type == PAYLOAD_TYPE_RPM_OSTREE:
            log.debug("Don't configure bootloader on rpm-ostree systems.")
            return

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


class CollectKernelArgumentsTask(Task):
    """Installation task for collecting the kernel arguments."""

    def __init__(self, storage, mode):
        """Create a new task."""
        super().__init__()
        self._storage = storage
        self._mode = mode

    @property
    def name(self):
        """Name of the task."""
        return "Collect kernel arguments"

    @property
    def _bootloader(self):
        """Representation of the bootloader."""
        return self._storage.bootloader

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

        log.debug("Collecting the kernel arguments.")

        stage1_device = self._bootloader.stage1_device
        log.info("boot loader stage1 target device is %s", stage1_device.name)

        stage2_device = self._bootloader.stage2_device
        log.info("boot loader stage2 target device is %s", stage2_device.name)

        self._bootloader.collect_arguments(self._storage)


class InstallBootloaderTask(Task):
    """Installation task for the bootloader."""

    def __init__(self, storage, mode, payload_type, sysroot):
        """Create a new task."""
        super().__init__()
        self._storage = storage
        self._mode = mode
        self._payload_type = payload_type
        self._sysroot = sysroot

    @property
    def name(self):
        """Name of the task."""
        return "Install the bootloader"

    @property
    def _bootloader(self):
        """Representation of the bootloader."""
        return self._storage.bootloader

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

        if self._payload_type == PAYLOAD_TYPE_RPM_OSTREE and have_bootupd(self._sysroot):
            log.debug("Will not install regular bootloader for ostree with bootupd")
            return

        log.debug("Installing the boot loader.")

        try:
            self._bootloader.prepare()
            self._bootloader.write()
        except BootLoaderError as e:
            log.exception("Bootloader installation has failed: %s", e)
            raise BootloaderInstallationError(str(e)) from None


class CreateBLSEntriesTask(Task):
    """The installation task that creates BLS entries."""

    def __init__(self, storage, payload_type, kernel_versions, sysroot):
        """Create a new task."""
        super().__init__()
        self._storage = storage
        self._payload_type = payload_type
        self._versions = kernel_versions
        self._sysroot = sysroot

    @property
    def name(self):
        return "Create the BLS entries"

    def run(self):
        """Run the task."""
        if self._payload_type not in PAYLOAD_LIVE_TYPES:
            log.debug("Only live payloads require this fix.")
            return

        create_bls_entries(
            sysroot=self._sysroot,
            storage=self._storage,
            kernel_versions=self._versions
        )


class RecreateInitrdsTask(Task):
    """Installation task that recreates the initrds."""

    def __init__(self, storage, payload_type, kernel_versions, sysroot):
        """Create a new task."""
        super().__init__()
        self._storage = storage
        self._payload_type = payload_type
        self._versions = kernel_versions
        self._sysroot = sysroot

    @property
    def name(self):
        return "Recreate the initrds"

    def run(self):
        """Run the task."""
        # For rpm-ostree payloads, we're replicating an initramfs
        # from a compose server, and should never be regenerating
        # them per-machine.
        if self._payload_type == PAYLOAD_TYPE_RPM_OSTREE:
            log.debug("Don't regenerate initramfs on rpm-ostree systems.")
            return
        if isinstance(self._storage.bootloader, SystemdBoot):
            log.debug("Don't regenerate initramfs on systemd-boot systems.")
            return

        recreate_initrds(
            sysroot=self._sysroot,
            kernel_versions=self._versions
        )


class FixBTRFSBootloaderTask(Task):
    """Installation task fixing the bootloader on BTRFS.

    This works around 2 problems, /boot on BTRFS and BTRFS installations
    where the initrd is recreated after the first writeBootLoader call.
    This reruns it after the new initrd has been created, fixing the
    kernel root and subvol args and adding the missing initrd entry.
    """

    def __init__(self, storage, mode, payload_type, kernel_versions, sysroot):
        """Create a new task."""
        super().__init__()
        self._storage = storage
        self._mode = mode
        self._payload_type = payload_type
        self._versions = kernel_versions
        self._sysroot = sysroot

    @property
    def name(self):
        return "Fix the bootloader on BTRFS"

    def run(self):
        """Run the task."""
        if self._payload_type not in PAYLOAD_LIVE_TYPES:
            log.debug("Only live payloads require this fix.")
            return

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
            self._payload_type,
            self._versions,
            self._sysroot
        ).run()

        InstallBootloaderTask(
            self._storage,
            self._mode,
            self._payload_type,
            self._sysroot
        ).run()


class FixZIPLBootloaderTask(Task):
    """Installation task fixing the ZIPL bootloader.

    Invoking zipl should be the last thing done on a s390x installation (see #1652727, #2022841).
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

        execWithRedirect("zipl", [], root=conf.target.system_root)
