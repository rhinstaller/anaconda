#
# platform.py:  Architecture-specific information
#
# Copyright (C) 2009-2011
# Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Authors: Chris Lumens <clumens@redhat.com>
#
from blivet import arch
from blivet.devicelibs import raid
from blivet.size import Size

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.i18n import N_, _
from pyanaconda.modules.storage.partitioning.specification import PartSpec

log = get_module_logger(__name__)

# Names of stage1 constrains.
PLATFORM_DEVICE_TYPES = "device_types"
PLATFORM_FORMAT_TYPES = "format_types"
PLATFORM_MOUNT_POINTS = "mountpoints"
PLATFORM_MAX_END = "max_end"
PLATFORM_RAID_LEVELS = "raid_levels"
PLATFORM_RAID_METADATA = "raid_metadata"

# Descriptions of stage1 bootloader devices.
PARTITION_DESCRIPTION = N_("First sector of boot partition")
RAID_DESCRIPTION = N_("RAID Device")
MBR_DESCRIPTION = N_("Master Boot Record")
EFI_DESCRIPTION = N_("EFI System Partition")
PREP_BOOT_DESCRIPTION = N_("PReP Boot Partition")
APPLE_BOOTSTRAP_DESCRIPTION = N_("Apple Bootstrap Partition")
DASD_DESCRIPTION = N_("DASD")
ZFCP_DESCRIPTION = N_("zFCP")


class Platform:
    """A base class for a platform.

    A class containing platform-specific information and methods for use
    during installation.  The intent is to eventually encapsulate all the
    architecture quirks in one place to avoid lots of platform checks
    throughout anaconda.
    """

    @property
    def packages(self):
        """Packages required for this platform.

        :return: a list of package names
        """
        return []

    @property
    def non_linux_format_types(self):
        """Format types of devices with non-linux operating systems."""
        return []

    @property
    def stage1_suggestion(self):
        """The platform-specific suggestion about the stage1 device.

        :return: a string
        """
        return _("You must include at least one disk as an install target.")

    @property
    def stage1_descriptions(self):
        """The platform-specific descriptions of the stage1 device.

        :return: a dictionary of device types and their descriptions
        """
        return {}

    @property
    def stage1_constraints(self):
        """The platform-specific constraints for the stage1 device.

        :return: a dictionary of constraints
        """
        return {
            PLATFORM_DEVICE_TYPES: [],
            PLATFORM_FORMAT_TYPES: [],
            PLATFORM_MOUNT_POINTS: [],
            PLATFORM_MAX_END: None,
            PLATFORM_RAID_LEVELS: [],
            PLATFORM_RAID_METADATA: [],
        }

    @property
    def partitions(self):
        """The default platform-specific partitions.

        :return: a list of specifications
        """
        partitions = [
            self._bootloader_partition,
            self._boot_partition
        ]
        return list(filter(None, partitions))

    @property
    def _bootloader_partition(self):
        """The default bootloader partition for this platform.

        Return the required platform-specific bootloader partition
        information. These are typically partitions that do not get
        mounted, like biosboot or prepboot, but may also include
        the /boot/efi partition.

        :return: a specification or None
        """
        return None

    @property
    def _boot_partition(self):
        """The default /boot partition for this platform.

        :return: a specification or None
        """
        return PartSpec(
            mountpoint="/boot",
            size=Size("1GiB")
        )


class X86(Platform):

    @property
    def non_linux_format_types(self):
        """Format types of devices with non-linux operating systems."""
        # XXX hpfs, if reported by blkid/udev, will end up with a type of None
        return ["vfat", "ntfs", "hpfs"]

    @property
    def stage1_suggestion(self):
        """The platform-specific suggestion about the stage1 device."""
        return _(
            "You must include at least one MBR- or "
            "GPT-formatted disk as an install target."
        )

    @property
    def stage1_descriptions(self):
        """The platform-specific descriptions of the stage1 device."""
        return {
            "disk": _(MBR_DESCRIPTION),
            "partition": _(PARTITION_DESCRIPTION),
            "mdarray": _(RAID_DESCRIPTION)
        }

    @property
    def stage1_constraints(self):
        """The platform-specific constraints for the stage1 device."""
        constraints = {
            PLATFORM_DEVICE_TYPES: ["disk"],
            PLATFORM_RAID_LEVELS: [raid.RAID1],
            PLATFORM_RAID_METADATA: ["1.0"]
        }
        return dict(super().stage1_constraints, **constraints)

    @property
    def _bootloader_partition(self):
        """The default bootloader partition for this platform."""
        return PartSpec(
            fstype="biosboot",
            size=Size("1MiB")
        )


class EFI(Platform):

    @property
    def non_linux_format_types(self):
        """Format types of devices with non-linux operating systems."""
        # XXX hpfs, if reported by blkid/udev, will end up with a type of None
        return ["vfat", "ntfs", "hpfs"]

    @property
    def stage1_suggestion(self):
        """The platform-specific suggestion about the stage1 device."""
        return _(
            "For a UEFI installation, you must include "
            "an EFI System Partition on a GPT-formatted "
            "disk, mounted at /boot/efi."
        )

    @property
    def stage1_descriptions(self):
        """The platform-specific descriptions of the stage1 device."""
        return {
            "partition": _(EFI_DESCRIPTION),
            "mdarray": _(RAID_DESCRIPTION)
        }

    @property
    def stage1_constraints(self):
        """The platform-specific constraints for the stage1 device."""
        constraints = {
            PLATFORM_FORMAT_TYPES: ["efi"],
            PLATFORM_DEVICE_TYPES: ["partition", "mdarray"],
            PLATFORM_MOUNT_POINTS: ["/boot/efi"],
            PLATFORM_RAID_LEVELS: [raid.RAID1],
            PLATFORM_RAID_METADATA: ["1.0"],
        }
        return dict(super().stage1_constraints, **constraints)

    @property
    def _bootloader_partition(self):
        """The default bootloader partition for this platform."""
        return PartSpec(
            mountpoint="/boot/efi",
            fstype="efi",
            size=Size("500MiB"),
            max_size=Size("600MiB"),
            grow=True
        )


class Aarch64EFI(EFI):

    @property
    def non_linux_format_types(self):
        """Format types of devices with non-linux operating systems."""
        return ["vfat", "ntfs"]


class ArmEFI(EFI):

    @property
    def non_linux_format_types(self):
        """Format types of devices with non-linux operating systems."""
        return ["vfat", "ntfs"]


class PPC(Platform):

    @property
    def stage1_constraints(self):
        """The platform-specific constraints for the stage1 device."""
        constraints = {
            PLATFORM_DEVICE_TYPES: ["partition"]
        }
        return dict(super().stage1_constraints, **constraints)


class IPSeriesPPC(PPC):

    @property
    def stage1_suggestion(self):
        """The platform-specific suggestion about the stage1 device."""
        return _(
            "You must include a PReP Boot Partition "
            "within the first 4GiB of an MBR- "
            "or GPT-formatted disk."
        )

    @property
    def stage1_descriptions(self):
        """The platform-specific descriptions of the stage1 device."""
        return {"partition": _(PREP_BOOT_DESCRIPTION)}

    @property
    def stage1_constraints(self):
        """The platform-specific constraints for the stage1 device."""
        constraints = {
            PLATFORM_FORMAT_TYPES: ["prepboot"],
            PLATFORM_MAX_END: Size("4 GiB")
        }
        return dict(super().stage1_constraints, **constraints)

    @property
    def _bootloader_partition(self):
        """The default bootloader partition for this platform."""
        return PartSpec(
            fstype="prepboot",
            size=Size("4MiB")
        )


class NewWorldPPC(PPC):

    @property
    def non_linux_format_types(self):
        """Format types of devices with non-linux operating systems."""
        return ["hfs", "hfs+"]

    @property
    def stage1_suggestion(self):
        """The platform-specific suggestion about the stage1 device."""
        return _(
            "You must include an Apple Bootstrap "
            "Partition on an Apple Partition Map-"
            "formatted disk."
        )

    @property
    def stage1_descriptions(self):
        """The platform-specific descriptions of the stage1 device."""
        return {"partition": _(APPLE_BOOTSTRAP_DESCRIPTION)}

    @property
    def stage1_constraints(self):
        """The platform-specific constraints for the stage1 device."""
        constraints = {
            PLATFORM_FORMAT_TYPES: ["appleboot"]
        }
        return dict(super().stage1_constraints, **constraints)

    @property
    def _bootloader_partition(self):
        """The default bootloader partition for this platform."""
        return PartSpec(
            fstype="appleboot",
            size=Size("1MiB")
        )


class PowerNV(PPC):

    @property
    def stage1_suggestion(self):
        """The platform-specific suggestion about the stage1 device."""
        return _("You must include at least one disk as an install target.")

    @property
    def stage1_descriptions(self):
        """The platform-specific descriptions of the stage1 device."""
        return {"partition": _(PARTITION_DESCRIPTION)}


class PS3(PPC):
    pass


class S390(Platform):

    @property
    def stage1_suggestion(self):
        """The platform-specific suggestion about the stage1 device."""
        return _(
            "You must include at least one MBR- or "
            "DASD-formatted disk as an install target."
        )

    @property
    def stage1_descriptions(self):
        """The platform-specific descriptions of the stage1 device."""
        return {
            "dasd": _(DASD_DESCRIPTION),
            "zfcp": _(ZFCP_DESCRIPTION),
            "disk": _(MBR_DESCRIPTION),
            "partition": _(PARTITION_DESCRIPTION)
        }

    @property
    def stage1_constraints(self):
        """The platform-specific constraints for the stage1 device."""
        constraints = {
            PLATFORM_DEVICE_TYPES: ["disk", "partition"]
        }
        return dict(super().stage1_constraints, **constraints)

    @property
    def _boot_partition(self):
        """The default /boot partition for this platform."""
        return PartSpec(
            mountpoint="/boot",
            size=Size("1GiB"),
            lv=False
        )


class ARM(Platform):

    @property
    def stage1_suggestion(self):
        """The platform-specific suggestion about the stage1 device."""
        return _(
            "You must include at least one MBR-formatted "
            "disk as an install target."
        )

    @property
    def stage1_descriptions(self):
        """The platform-specific descriptions of the stage1 device."""
        return {
            "disk": _(MBR_DESCRIPTION),
            "partition": _(PARTITION_DESCRIPTION)
        }

    @property
    def stage1_constraints(self):
        """The platform-specific constraints for the stage1 device."""
        constraints = {
            PLATFORM_DEVICE_TYPES: ["disk"]
        }
        return dict(super().stage1_constraints, **constraints)


class RISCV64(Platform):

    @property
    def stage1_suggestion(self):
        """The platform-specific suggestion about the stage1 device."""
        return _(
            "You must include at least one MBR-formatted "
            "disk as an install target."
        )

    @property
    def stage1_descriptions(self):
        """The platform-specific descriptions of the stage1 device."""
        return {
            "disk": _(MBR_DESCRIPTION),
            "partition": _(PARTITION_DESCRIPTION)
        }

    @property
    def stage1_constraints(self):
        """The platform-specific constraints for the stage1 device."""
        constraints = {
            PLATFORM_DEVICE_TYPES: ["disk"]
        }
        return dict(super().stage1_constraints, **constraints)


class RISCV64EFI(EFI):

    @property
    def non_linux_format_types(self):
        """Format types of devices with non-linux operating systems."""
        return ["vfat", "ntfs"]


def get_platform():
    """Check the architecture of the system and return an instance of a
       Platform subclass to match.  If the architecture could not be determined,
       raise an exception."""
    if arch.is_ppc():
        ppc_machine = arch.get_ppc_machine()

        if ppc_machine == "PMac" and arch.get_ppc_mac_gen() == "NewWorld":
            return NewWorldPPC()
        elif ppc_machine in ["iSeries", "pSeries"]:
            return IPSeriesPPC()
        elif ppc_machine == "PowerNV":
            return PowerNV()
        elif ppc_machine == "PS3":
            return PS3()
        else:
            raise SystemError("Unsupported PPC machine type: %s" % ppc_machine)
    elif arch.is_s390():
        return S390()
    elif arch.is_efi():
        if arch.is_aarch64():
            return Aarch64EFI()
        elif arch.is_arm():
            return ArmEFI()
        elif arch.is_riscv64():
            return RISCV64EFI()
        else:
            return EFI()
    elif arch.is_x86():
        return X86()
    elif arch.is_arm():
        return ARM()
    elif arch.is_riscv64():
        return RISCV64()
    else:
        raise SystemError("Could not determine system architecture.")


platform = get_platform()
