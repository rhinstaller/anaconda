#
# DBus interface for the bootloader module.
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
from dasbus.server.interface import dbus_interface
from dasbus.server.property import emits_properties_changed
from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.modules.common.base import KickstartModuleInterfaceTemplate
from pyanaconda.modules.common.constants.objects import BOOTLOADER
from pyanaconda.modules.common.containers import TaskContainer
from pyanaconda.modules.storage.constants import BootloaderMode, ZIPLSecureBoot


@dbus_interface(BOOTLOADER.interface_name)
class BootloaderInterface(KickstartModuleInterfaceTemplate):
    """DBus interface for the bootloader module."""

    def connect_signals(self):
        """Connect the signals."""
        super().connect_signals()
        self.watch_property("BootloaderMode", self.implementation.bootloader_mode_changed)
        self.watch_property("PreferredLocation", self.implementation.preferred_location_changed)
        self.watch_property("Drive", self.implementation.drive_changed)
        self.watch_property("DriveOrder", self.implementation.drive_order_changed)
        self.watch_property("KeepMBR", self.implementation.keep_mbr_changed)
        self.watch_property("KeepBootOrder", self.implementation.keep_boot_order_changed)
        self.watch_property("ExtraArguments", self.implementation.extra_arguments_changed)
        self.watch_property("Timeout", self.implementation.timeout_changed)
        self.watch_property("ZIPLSecureBoot", self.implementation.zipl_secure_boot_changed)
        self.watch_property("IsPasswordSet", self.implementation.password_is_set_changed)

    def GetDefaultType(self) -> Str:
        """Get the default type of the boot loader.

        FIXME: This is a temporary workaround for UI.

        :return: a name of a boot loader type
        """
        return self.implementation.get_default_type().value

    @property
    def BootloaderMode(self) -> Int:
        """The mode of the bootloader."""
        return self.implementation.bootloader_mode.value

    @BootloaderMode.setter
    @emits_properties_changed
    def BootloaderMode(self, mode: Int):
        """Set the type of the bootloader.

        Allowed values:
            0  Disabled.
            1  Enabled.
            2  Skipped.

        The skipped mode prevents extra installation steps that makes
        the target machine bootable, e.g. write to MBR on x86 BIOS
        systems. However, the corresponding RPM packages are still
        installed. The disabled mode also prevents the installation
        of RPM packages.

        :param mode: a number of the mode
        """
        self.implementation.set_bootloader_mode(BootloaderMode(mode))

    @property
    def PreferredLocation(self) -> Str:
        """Where the boot record is written."""
        return self.implementation.preferred_location

    @PreferredLocation.setter
    @emits_properties_changed
    def PreferredLocation(self, location: Str):
        """Specify where the boot record is written.

        Supported values:
            DEFAULT    The default location.
            MBR        The master boot record.
            PARTITION  Install the boot loader on the first sector of
                       the partition containing the kernel.

        :param location: a string with a location
        """
        self.implementation.set_preferred_location(location)

    @property
    def Drive(self) -> Str:
        """The drive where the bootloader should be written."""
        return self.implementation.drive

    @Drive.setter
    @emits_properties_changed
    def Drive(self, drive: Str):
        """Set the drive where the bootloader should be written.

        Specifies which drive the bootloader should be written to and
        thus, which drive the computer will boot from.

        :param drive: a name of the drive
        """
        self.implementation.set_drive(drive)

    @property
    def DriveOrder(self) -> List[Str]:
        """Potentially partial order for disks."""
        return self.implementation.drive_order

    @DriveOrder.setter
    @emits_properties_changed
    def DriveOrder(self, drives: List[Str]):
        """Set the potentially partial order for disks.

        :param drives: a list of names of drives
        """
        self.implementation.set_drive_order(drives)

    @property
    def KeepMBR(self) -> Bool:
        """Don't update the MBR."""
        return self.implementation.keep_mbr

    @KeepMBR.setter
    @emits_properties_changed
    def KeepMBR(self, value: Bool):
        """Set if the MBR can be updated.

        If you want to keep the MBR, then the bootloader will be installed
        but the MBR will not be updated. Therefore, when the system reboots,
        a previously installed OS will be booted.

        :param value: True if the MBR cannot be updated, otherwise False
        """
        self.implementation.set_keep_mbr(value)

    @property
    def KeepBootOrder(self) -> Bool:
        """Don't change the existing boot order."""
        return self.implementation.keep_boot_order

    @KeepBootOrder.setter
    @emits_properties_changed
    def KeepBootOrder(self, value: Bool):
        """Set if the the boot order can be changed.

        Boot the drives in their existing order, to override the default
        of booting into the newly installed drive on Power Systems servers
        and EFI systems. This is useful for systems that, for example,
        should network boot first before falling back to a local boot.

        :param value: True to use the existing order, otherwise False
        """
        self.implementation.set_keep_boot_order(value)

    @property
    def ExtraArguments(self) -> List[Str]:
        """List of extra bootloader arguments."""
        return self.implementation.extra_arguments

    @ExtraArguments.setter
    @emits_properties_changed
    def ExtraArguments(self, args: List[Str]):
        """Set the extra bootloader arguments.

        Specifies kernel parameters. The default set of bootloader
        arguments is “rhgb quiet”. You will get this set of arguments
        regardless of what extra parameters you set.

        :param args: list of arguments
        """
        self.implementation.set_extra_arguments(args)

    @property
    def Timeout(self) -> Int:
        """The bootloader timeout."""
        return self.implementation.timeout

    @Timeout.setter
    @emits_properties_changed
    def Timeout(self, timeout: Int):
        """Set the bootloader timeout.

        Specify the number of seconds before the bootloader times out
        and boots the default option.

        :param timeout: a number of seconds
        """
        self.implementation.set_timeout(timeout)

    @property
    def ZIPLSecureBoot(self) -> Str:
        """The ZIPL Secure Boot for s390x."""
        return self.implementation.zipl_secure_boot.value

    @ZIPLSecureBoot.setter
    @emits_properties_changed
    def ZIPLSecureBoot(self, value: Str):
        """Set up the ZIPL Secure Boot for s390x.

        Supported values:
            0     Disable Secure Boot.
            1     Enable Secure Boot (or fail if unsupported).
            auto  Enable Secure Boot if supported.

        Firmware will verify the integrity of the Linux kernel during
        boot if the Secure Boot is enabled and configured on the machine.

        Note: Secure Boot is not supported on IBM z14 and earlier models,
        therefore choose to disable it if you intend to boot the installed
        system on such models.

        :param value: a string
        """
        self.implementation.set_zipl_secure_boot(ZIPLSecureBoot(value))

    @property
    def Password(self) -> Str:
        """The GRUB boot loader password.

        If using GRUB, set the GRUB boot loader password. This should
        be used to restrict access to the GRUB shell, where arbitrary
        kernel options can be passed.
        """
        return self.implementation.password

    @emits_properties_changed
    def SetEncryptedPassword(self, password: Str):
        """Set the GRUB boot loader password.

        :param password: a string with the encrypted password
        """
        self.implementation.set_password(password, encrypted=True)

    @property
    def IsPasswordSet(self) -> Bool:
        """Is the GRUB boot loader password set?"""
        return self.implementation.password_is_set

    @property
    def IsPasswordEncrypted(self) -> Bool:
        """Is the GRUB boot loader password encrypted?"""
        return self.implementation.password_is_encrypted

    def IsEFI(self) -> Bool:
        """Is the bootloader based on EFI?

        :return: True or False
        """
        return self.implementation.is_efi()

    def GetArguments(self) -> List[Str]:
        """Get the bootloader arguments.

        Get kernel parameters that are currently set up for the bootloader.
        The list is complete and final after the bootloader installation.

        :return: list of arguments
        """
        return self.implementation.get_arguments()

    def DetectWindows(self) -> Bool:
        """Are Windows OS installed on the system?

        Guess by searching for bootable partitions of other operating
        systems whether there are Windows OS installed on the system.

        :return: True or False
        """
        return self.implementation.detect_windows()

    def InstallBootloaderWithTasks(self, payload_type: Str, kernel_versions: List[Str]) \
            -> List[ObjPath]:
        """Install the bootloader with a list of tasks.

        FIXME: This is just a temporary method.

        :param payload_type: a string with the payload type
        :param kernel_versions: a list of kernel versions
        :return: a list of paths to DBus tasks
        """
        tasks = self.implementation.install_bootloader_with_tasks(
            payload_type,
            kernel_versions
        )
        return TaskContainer.to_object_path_list(tasks)

    def GenerateInitramfsWithTasks(self, payload_type: Str, kernel_versions: List[Str]) \
            -> List[ObjPath]:
        """Generate initramfs with a list of tasks.

        FIXME: This is just a temporary method.

        :param payload_type: a string with the payload type
        :param kernel_versions: a list of kernel versions
        :return: a list of paths to DBus tasks
        """
        tasks = self.implementation.generate_initramfs_with_tasks(
            payload_type,
            kernel_versions
        )
        return TaskContainer.to_object_path_list(tasks)

    def FixZIPLBootloaderWithTask(self) -> ObjPath:
        """Fix ZIPL bootloader with a task.

        :return: a DBus path of a installation task
        """
        return TaskContainer.to_object_path(
            self.implementation.fix_zipl_bootloader_with_task()
        )
