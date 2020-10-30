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
from pyanaconda.core.i18n import _, N_
from pyanaconda.modules.storage.partitioning.specification import PartSpec

log = get_module_logger(__name__)


class Platform(object):
    """Platform

       A class containing platform-specific information and methods for use
       during installation.  The intent is to eventually encapsulate all the
       architecture quirks in one place to avoid lots of platform checks
       throughout anaconda."""

    # requirements for bootloader stage1 devices
    _boot_stage1_device_types = []
    _boot_stage1_format_types = []
    _boot_stage1_mountpoints = []
    _boot_stage1_max_end = None
    _boot_stage1_raid_levels = []
    _boot_stage1_raid_metadata = []
    _boot_stage1_raid_member_types = []
    _boot_stage1_description = N_("boot loader device")
    _boot_raid_description = N_("RAID Device")
    _boot_partition_description = N_("First sector of boot partition")
    _boot_descriptions = {}

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
    def boot_stage1_constraint_dict(self):
        d = {"device_types": self._boot_stage1_device_types,
             "format_types": self._boot_stage1_format_types,
             "mountpoints": self._boot_stage1_mountpoints,
             "max_end": self._boot_stage1_max_end,
             "raid_levels": self._boot_stage1_raid_levels,
             "raid_metadata": self._boot_stage1_raid_metadata,
             "raid_member_types": self._boot_stage1_raid_member_types,
             "descriptions": dict((k, _(v)) for k, v in self._boot_descriptions.items())}
        return d

    def set_platform_bootloader_reqs(self):
        """Return the required platform-specific bootloader partition
           information.  These are typically partitions that do not get mounted,
           like biosboot or prepboot, but may also include the /boot/efi
           partition."""
        return []

    def set_platform_boot_partition(self):
        """Return the default /boot partition for this platform."""
        return [PartSpec(mountpoint="/boot", size=Size("1GiB"))]

    def set_default_partitioning(self):
        """Return the default platform-specific partitioning information."""
        return self.set_platform_bootloader_reqs() + self.set_platform_boot_partition()

    @property
    def stage1_suggestion(self):
        """The platform-specific suggestion about the stage1 device.

        :return: a string
        """
        return _("You must include at least one disk as an install target.")


class X86(Platform):
    _boot_stage1_device_types = ["disk"]
    _boot_mbr_description = N_("Master Boot Record")
    _boot_descriptions = {"disk": _boot_mbr_description,
                          "partition": Platform._boot_partition_description,
                          "mdarray": Platform._boot_raid_description}

    @property
    def non_linux_format_types(self):
        """Format types of devices with non-linux operating systems."""
        # XXX hpfs, if reported by blkid/udev, will end up with a type of None
        return ["vfat", "ntfs", "hpfs"]

    def set_platform_bootloader_reqs(self):
        """Return the default platform-specific partitioning information."""
        ret = Platform.set_platform_bootloader_reqs(self)
        ret.append(PartSpec(fstype="biosboot", size=Size("1MiB")))
        return ret

    @property
    def stage1_suggestion(self):
        """The platform-specific suggestion about the stage1 device."""
        return _(
            "You must include at least one MBR- or "
            "GPT-formatted disk as an install target."
        )


class EFI(Platform):

    _boot_stage1_format_types = ["efi"]
    _boot_stage1_device_types = ["partition", "mdarray"]
    _boot_stage1_mountpoints = ["/boot/efi"]
    _boot_stage1_raid_levels = [raid.RAID1]
    _boot_stage1_raid_metadata = ["1.0"]
    _boot_efi_description = N_("EFI System Partition")
    _boot_descriptions = {"partition": _boot_efi_description,
                          "mdarray": Platform._boot_raid_description}

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

    def set_platform_bootloader_reqs(self):
        ret = Platform.set_platform_bootloader_reqs(self)
        ret.append(PartSpec(mountpoint="/boot/efi", fstype="efi",
                            size=Size("200MiB"), max_size=Size("600MiB"),
                            grow=True))
        return ret


class MacEFI(EFI):
    _boot_stage1_format_types = ["macefi"]
    _boot_efi_description = N_("Apple EFI Boot Partition")
    _boot_descriptions = {"partition": _boot_efi_description,
                          "mdarray": Platform._boot_raid_description}

    @property
    def packages(self):
        """Packages required for this platform."""
        return ["mactel-boot"]

    @property
    def non_linux_format_types(self):
        """Format types of devices with non-linux operating systems."""
        return ["macefi"]

    @property
    def stage1_suggestion(self):
        """The platform-specific suggestion about the stage1 device."""
        return _(
            "For a UEFI installation, you must include "
            "a Linux HFS+ ESP on a GPT-formatted "
            "disk, mounted at /boot/efi."
        )

    def set_platform_bootloader_reqs(self):
        ret = Platform.set_platform_bootloader_reqs(self)
        ret.append(PartSpec(mountpoint="/boot/efi", fstype="macefi",
                            size=Size("200MiB"), max_size=Size("600MiB"),
                            grow=True))
        return ret


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
    _boot_stage1_device_types = ["partition"]


class IPSeriesPPC(PPC):
    _boot_stage1_format_types = ["prepboot"]
    _boot_stage1_max_end = Size("4 GiB")
    _boot_prep_description = N_("PReP Boot Partition")
    _boot_descriptions = {"partition": _boot_prep_description}

    @property
    def stage1_suggestion(self):
        """The platform-specific suggestion about the stage1 device."""
        return _(
            "You must include a PReP Boot Partition "
            "within the first 4GiB of an MBR- "
            "or GPT-formatted disk."
        )

    def set_platform_bootloader_reqs(self):
        ret = PPC.set_platform_bootloader_reqs(self)
        ret.append(PartSpec(fstype="prepboot", size=Size("4MiB")))
        return ret


class NewWorldPPC(PPC):
    _boot_stage1_format_types = ["appleboot"]
    _boot_apple_description = N_("Apple Bootstrap Partition")
    _boot_descriptions = {"partition": _boot_apple_description}

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

    def set_platform_bootloader_reqs(self):
        ret = Platform.set_platform_bootloader_reqs(self)
        ret.append(PartSpec(fstype="appleboot", size=Size("1MiB")))
        return ret


class PowerNV(PPC):
    _boot_descriptions = {"partition": Platform._boot_partition_description}

    @property
    def stage1_suggestion(self):
        """The platform-specific suggestion about the stage1 device."""
        return _("You must include at least one disk as an install target.")


class PS3(PPC):
    pass


class S390(Platform):
    _boot_stage1_device_types = ["disk", "partition"]
    _boot_dasd_description = N_("DASD")
    _boot_mbr_description = N_("Master Boot Record")
    _boot_zfcp_description = N_("zFCP")
    _boot_descriptions = {"dasd": _boot_dasd_description,
                          "zfcp": _boot_zfcp_description,
                          "disk": _boot_mbr_description,
                          "partition": Platform._boot_partition_description}

    @property
    def packages(self):
        """Packages required for this platform."""
        return ["s390utils"]

    @property
    def stage1_suggestion(self):
        """The platform-specific suggestion about the stage1 device."""
        return _(
            "You must include at least one MBR- or "
            "DASD-formatted disk as an install target."
        )

    def set_platform_boot_partition(self):
        """Return the default platform-specific partitioning information."""
        return [PartSpec(mountpoint="/boot", size=Size("1GiB"), lv=False)]


class ARM(Platform):
    _boot_stage1_device_types = ["disk"]
    _boot_mbr_description = N_("Master Boot Record")
    _boot_descriptions = {"disk": _boot_mbr_description,
                          "partition": Platform._boot_partition_description}

    @property
    def stage1_suggestion(self):
        """The platform-specific suggestion about the stage1 device."""
        return _(
            "You must include at least one MBR-formatted "
            "disk as an install target."
        )


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
        if arch.is_mactel():
            return MacEFI()
        elif arch.is_aarch64():
            return Aarch64EFI()
        elif arch.is_arm():
            return ArmEFI()
        else:
            return EFI()
    elif arch.is_x86():
        return X86()
    elif arch.is_arm():
        return ARM()
    else:
        raise SystemError("Could not determine system architecture.")


platform = get_platform()
