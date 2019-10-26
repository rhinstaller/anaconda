#
# Bootloader module.
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
from pykickstart.errors import KickstartParseError

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.bootloader import get_bootloader_class
from pyanaconda.bootloader.efi import EFIBase
from pyanaconda.bootloader.grub2 import GRUB2
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import BOOTLOADER_LOCATION_DEFAULT, BOOTLOADER_TIMEOUT_UNSET, \
    BOOTLOADER_LOCATION_MBR, BOOTLOADER_LOCATION_PARTITION
from pyanaconda.core.i18n import _
from pyanaconda.core.dbus import DBus
from pyanaconda.core.signal import Signal
from pyanaconda.modules.common.base import KickstartBaseModule
from pyanaconda.modules.common.constants.objects import BOOTLOADER
from pyanaconda.modules.common.errors.storage import UnavailableStorageError
from pyanaconda.modules.common.structures.requirement import Requirement
from pyanaconda.modules.storage.bootloader.bootloader_interface import BootloaderInterface
from pyanaconda.modules.storage.bootloader.installation import ConfigureBootloaderTask, \
    InstallBootloaderTask, FixZIPLBootloaderTask, FixBTRFSBootloaderTask
from pyanaconda.modules.storage.constants import BootloaderMode, BootloaderType

log = get_module_logger(__name__)


class BootloaderModule(KickstartBaseModule):
    """The bootloader module."""

    def __init__(self):
        """Initialize the module."""
        super().__init__()
        self._current_storage = None

        self.bootloader_mode_changed = Signal()
        self._bootloader_mode = BootloaderMode.ENABLED

        self.bootloader_type_changed = Signal()
        self._bootloader_type = BootloaderType.DEFAULT

        self.preferred_location_changed = Signal()
        self._preferred_location = BOOTLOADER_LOCATION_DEFAULT

        self.drive_changed = Signal()
        self._drive = ""

        self.drive_order_changed = Signal()
        self._drive_order = []

        self.keep_mbr_changed = Signal()
        self._keep_mbr = False

        self.keep_boot_order_changed = Signal()
        self._keep_boot_order = False

        self.extra_arguments_changed = Signal()
        self._extra_arguments = []

        self.timeout_changed = Signal()
        self._timeout = BOOTLOADER_TIMEOUT_UNSET

        self.password_is_set_changed = Signal()
        self._password = ""
        self._password_is_encrypted = False

    @property
    def storage(self):
        """The storage model.

        :return: an instance of Blivet
        """
        if self._current_storage is None:
            raise UnavailableStorageError()

        return self._current_storage

    def on_storage_reset(self, storage):
        """Keep the instance of the current storage."""
        self._current_storage = storage

    def publish(self):
        """Publish the module."""
        DBus.publish_object(BOOTLOADER.object_path, BootloaderInterface(self))

    def process_kickstart(self, data):
        """Process the kickstart data."""
        self._set_module_from_kickstart(data)
        self._validate_grub2_configuration(data)

    def _set_module_from_kickstart(self, data):
        """Set the module from the kickstart data."""
        if not data.bootloader.seen:
            self.set_bootloader_mode(BootloaderMode.ENABLED)
            self.set_preferred_location(BOOTLOADER_LOCATION_DEFAULT)
        elif data.bootloader.disabled:
            self.set_bootloader_mode(BootloaderMode.DISABLED)
        elif data.bootloader.location == "none":
            self.set_bootloader_mode(BootloaderMode.SKIPPED)
        elif data.bootloader.location == "mbr":
            self.set_bootloader_mode(BootloaderMode.ENABLED)
            self.set_preferred_location(BOOTLOADER_LOCATION_MBR)
        elif data.bootloader.location == "partition":
            self.set_bootloader_mode(BootloaderMode.ENABLED)
            self.set_preferred_location(BOOTLOADER_LOCATION_PARTITION)

        if data.bootloader.extlinux:
            self.set_bootloader_type(BootloaderType.EXTLINUX)

        if data.bootloader.bootDrive:
            self.set_drive(data.bootloader.bootDrive)

        if data.bootloader.driveorder:
            self.set_drive_order(data.bootloader.driveorder)

        if data.bootloader.nombr:
            self.set_keep_mbr(True)

        if data.bootloader.leavebootorder:
            self.set_keep_boot_order(True)

        if data.bootloader.appendLine:
            args = data.bootloader.appendLine.split()
            self.set_extra_arguments(args)

        if data.bootloader.timeout is not None:
            self.set_timeout(data.bootloader.timeout)

        if data.bootloader.password:
            self.set_password(data.bootloader.password, data.bootloader.isCrypted)

    def _validate_grub2_configuration(self, data):
        """Validate the GRUB2 configuration.

        :raise: KickstartParseError if not valid
        """
        # Skip other types of the bootloader.
        if self.bootloader_type is not BootloaderType.DEFAULT:
            return

        if not issubclass(get_bootloader_class(), GRUB2):
            return

        # Check the location support.
        if self.preferred_location == BOOTLOADER_LOCATION_PARTITION:
            raise KickstartParseError(_("GRUB2 does not support installation to a partition."),
                                      lineno=data.bootloader.lineno)

        # Check the password format.
        if self.password_is_set \
                and self.password_is_encrypted \
                and not self.password.startswith("grub.pbkdf2."):
            raise KickstartParseError(_("GRUB2 encrypted password must be in grub.pbkdf2 format."),
                                      lineno=data.bootloader.lineno)

    def setup_kickstart(self, data):
        """Setup the kickstart data."""

        if self.bootloader_type == BootloaderType.EXTLINUX:
            data.bootloader.extlinux = True

        if self.bootloader_mode == BootloaderMode.DISABLED:
            data.bootloader.disabled = True
            data.bootloader.location = "none"
        elif self.bootloader_mode == BootloaderMode.SKIPPED:
            data.bootloader.disabled = False
            data.bootloader.location = "none"
        elif self.preferred_location == BOOTLOADER_LOCATION_MBR:
            data.bootloader.disabled = False
            data.bootloader.location = "mbr"
        elif self.preferred_location == BOOTLOADER_LOCATION_PARTITION:
            data.bootloader.disabled = False
            data.bootloader.location = "partition"
        else:
            data.bootloader.disabled = False
            data.bootloader.location = None

        data.bootloader.bootDrive = self.drive
        data.bootloader.driveorder = self.drive_order
        data.bootloader.nombr = self.keep_mbr
        data.bootloader.leavebootorder = self.keep_boot_order
        data.bootloader.appendLine = " ".join(self.extra_arguments)

        if self.timeout == BOOTLOADER_TIMEOUT_UNSET:
            data.bootloader.timeout = None
        else:
            data.bootloader.timeout = self.timeout

        data.bootloader.password = self.password
        data.bootloader.isCrypted = self.password_is_encrypted

        return data

    @property
    def bootloader_mode(self):
        """The mode of the bootloader."""
        return self._bootloader_mode

    def set_bootloader_mode(self, mode):
        """Set the type of the bootloader.

        :param mode: an instance of BootloaderMode
        """
        self._bootloader_mode = mode
        self.bootloader_mode_changed.emit()
        log.debug("Bootloader mode is set to '%s'.", mode)

    @property
    def bootloader_type(self):
        """The type of the bootloader."""
        return self._bootloader_type

    def set_bootloader_type(self, bootloader_type):
        """Set the type of the bootloader.

        :param bootloader_type: an instance of BootloaderType
        """
        self._bootloader_type = bootloader_type
        self.bootloader_type_changed.emit()
        log.debug("Bootloader type is set to '%s'.", bootloader_type)

    @property
    def preferred_location(self):
        """Where the boot record is written."""
        return self._preferred_location

    def set_preferred_location(self, location):
        """Specify where the boot record is written.

        Supported values: DEFAULT, MBR, PARTITION

        :param location: a string with the location
        """
        self._preferred_location = location
        self.preferred_location_changed.emit()
        log.debug("Preferred location is set to '%s'.", location)

    @property
    def drive(self):
        """The drive where the bootloader should be written."""
        return self._drive

    def set_drive(self, drive):
        """Set the drive where the bootloader should be written.

        :param drive: a name of the drive
        """
        self._drive = drive
        self.drive_changed.emit()
        log.debug("Drive is set to '%s'.", drive)

    @property
    def drive_order(self):
        """Potentially partial order for disks."""
        return self._drive_order

    def set_drive_order(self, drives):
        """Set the potentially partial order for disks.

        :param drives: a list of names of drives
        """
        self._drive_order = drives
        self.drive_order_changed.emit()
        log.debug("Drive order is set to '%s'.", drives)

    @property
    def keep_mbr(self):
        """Don't update the MBR."""
        return self._keep_mbr

    def set_keep_mbr(self, value):
        """Set if the MBR can be updated.

        :param value: True if the MBR cannot be updated, otherwise False
        """
        self._keep_mbr = value
        self.keep_mbr_changed.emit()
        log.debug("Keep MBR is set to '%s'.", value)

    @property
    def keep_boot_order(self):
        """Don't change the existing boot order."""
        return self._keep_boot_order

    def set_keep_boot_order(self, value):
        """Set if the the boot order can be changed.

        :param value: True to use the existing order, otherwise False
        :return:
        """
        self._keep_boot_order = value
        self.keep_boot_order_changed.emit()
        log.debug("Keep boot order is set to '%s'.", value)

    @property
    def extra_arguments(self):
        """List of extra bootloader arguments."""
        return self._extra_arguments

    def set_extra_arguments(self, args):
        """Set the extra bootloader arguments.

        :param args: a list of arguments
        """
        self._extra_arguments = args
        self.extra_arguments_changed.emit()
        log.debug("Extra arguments are set to '%s'.", args)

    @property
    def timeout(self):
        """The bootloader timeout."""
        return self._timeout

    def set_timeout(self, timeout):
        """Set the bootloader timeout.

        :param timeout: a number of seconds
        """
        self._timeout = timeout
        self.timeout_changed.emit()
        log.debug("Timeout is set to '%s'.", timeout)

    @property
    def password(self):
        """The GRUB boot loader password."""
        return self._password

    @property
    def password_is_set(self):
        """Is the GRUB boot loader password set?"""
        return self._password != ""

    @property
    def password_is_encrypted(self):
        """Is the GRUB boot loader password encrypted?"""
        return self._password_is_encrypted

    def set_password(self, password, encrypted):
        """Set the GRUB boot loader password.

        :param password: a string with the password
        :param encrypted: True if the password is encrypted, otherwise False
        """
        self._password = password
        self._password_is_encrypted = encrypted
        self.password_is_set_changed.emit()
        log.debug("Password is set.")

    def is_efi(self):
        """Is the bootloader based on EFI?

        :return: True or False
        """
        return isinstance(self.storage.bootloader, EFIBase)

    def get_arguments(self):
        """Get the bootloader arguments.

        Get kernel parameters that are currently set up for the bootloader.
        The list is complete and final after the bootloader installation.

        FIXME: Collect the bootloader arguments on demand if possible.

        :return: list of arguments
        """
        return list(self.storage.bootloader.boot_args)

    def detect_windows(self):
        """Are Windows OS installed on the system?

        Guess by searching for bootable partitions of other operating
        systems whether there are Windows OS installed on the system.

        :return: True or False
        """
        devices = filter(lambda d: d.format.name == "ntfs", self.storage.devices)
        return self.storage.bootloader.has_windows(devices)

    def collect_requirements(self):
        """Return installation requirements for this module.

        :return: a list of requirements
        """
        if conf.target.is_directory:
            log.debug("The bootloader configuration is disabled for dir installations.")
            return []

        if self.bootloader_mode == BootloaderMode.DISABLED:
            log.debug("The bootloader configuration is disabled.")
            return []

        requirements = []

        for name in self.storage.bootloader.packages:
            requirements.append(Requirement.for_package(
                name, reason="Necessary for the bootloader configuration."
            ))

        return requirements

    def configure_with_task(self, kernel_versions):
        """Configure the bootloader.

        FIXME: This is just a temporary method.

        :param kernel_versions: a list of kernel versions
        :return: a task
        """
        return ConfigureBootloaderTask(
            storage=self.storage,
            mode=self.bootloader_mode,
            kernel_versions=kernel_versions,
            sysroot=conf.target.system_root
        )

    def install_with_task(self):
        """Install the bootloader.

        FIXME: This is just a temporary method.

        :return: a task
        """
        return InstallBootloaderTask(
            storage=self.storage,
            mode=self.bootloader_mode
        )

    def fix_btrfs_with_task(self, kernel_versions):
        """Fix the bootloader on BTRFS.

        FIXME: This is just a temporary method.

        :param kernel_versions: a list of kernel versions
        :return: a task
        """
        return FixBTRFSBootloaderTask(
            storage=self.storage,
            mode=self.bootloader_mode,
            kernel_versions=kernel_versions,
            sysroot=conf.target.system_root
        )

    def fix_zipl_with_task(self):
        """Fix the ZIPL bootloader.

        FIXME: This is just a temporary method.

        :return: a task
        """
        return FixZIPLBootloaderTask(
            mode=self.bootloader_mode
        )
