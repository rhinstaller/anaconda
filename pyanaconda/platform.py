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
import logging
log = logging.getLogger("anaconda.storage")

from blivet import arch
from blivet.devicelibs import raid
from blivet.formats import get_device_format_class
from blivet.size import Size
from pyanaconda.core.i18n import _, N_
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.modules.storage.partitioning.specification import PartSpec


class Platform(object):

    """Platform

       A class containing platform-specific information and methods for use
       during installation.  The intent is to eventually encapsulate all the
       architecture quirks in one place to avoid lots of platform checks
       throughout anaconda."""
    _packages = []

    # requirements for bootloader stage1 devices
    _boot_stage1_device_types = []
    _boot_stage1_format_types = []
    _boot_stage1_mountpoints = []
    _boot_stage1_max_end = None
    _boot_stage1_raid_levels = []
    _boot_stage1_raid_metadata = []
    _boot_stage1_raid_member_types = []
    _boot_stage1_description = N_("boot loader device")
    _boot_stage1_missing_error = ""
    _boot_raid_description = N_("RAID Device")
    _boot_partition_description = N_("First sector of boot partition")
    _boot_descriptions = {}

    _non_linux_format_types = []

    def __init__(self):
        """Creates a new Platform object.  This is basically an abstract class.
           You should instead use one of the platform-specific classes as
           returned by get_platform below.  Not all subclasses need to provide
           all the methods in this class."""

        self.update_from_flags()

    def update_from_flags(self):
        if conf.storage.gpt:
            disklabel_class = get_device_format_class("disklabel")
            disklabel_types = disklabel_class.get_platform_label_types()
            if "gpt" not in disklabel_types:
                log.warning("GPT is not a supported disklabel on this platform. Using default "
                            "disklabel %s instead.", disklabel_types[0])
            else:
                disklabel_class.set_default_label_type("gpt")

    def __call__(self):
        return self

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

    @property
    def packages(self):
        _packages = self._packages
        return _packages

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
    def stage1_missing_error(self):
        """A platform-specific error message to be shown if stage1 target
           selection fails."""
        return self._boot_stage1_missing_error


class X86(Platform):
    _boot_stage1_device_types = ["disk"]
    _boot_mbr_description = N_("Master Boot Record")
    _boot_descriptions = {"disk": _boot_mbr_description,
                          "partition": Platform._boot_partition_description,
                          "mdarray": Platform._boot_raid_description}

    # XXX hpfs, if reported by blkid/udev, will end up with a type of None
    _non_linux_format_types = ["vfat", "ntfs", "hpfs"]
    _boot_stage1_missing_error = N_("You must include at least one MBR- or "
                                    "GPT-formatted disk as an install target.")

    def set_platform_bootloader_reqs(self):
        """Return the default platform-specific partitioning information."""
        ret = super().set_platform_bootloader_reqs()
        ret.append(PartSpec(fstype="biosboot", size=Size("1MiB")))
        return ret


class EFI(Platform):

    _boot_stage1_format_types = ["efi"]
    _boot_stage1_device_types = ["partition", "mdarray"]
    _boot_stage1_mountpoints = ["/boot/efi"]
    _boot_stage1_raid_levels = [raid.RAID1]
    _boot_stage1_raid_metadata = ["1.0"]
    _boot_efi_description = N_("EFI System Partition")
    _boot_descriptions = {"partition": _boot_efi_description,
                          "mdarray": Platform._boot_raid_description}

    # XXX hpfs, if reported by blkid/udev, will end up with a type of None
    _non_linux_format_types = ["vfat", "ntfs", "hpfs"]
    _boot_stage1_missing_error = N_("For a UEFI installation, you must include "
                                    "an EFI System Partition on a GPT-formatted "
                                    "disk, mounted at /boot/efi.")

    def set_platform_bootloader_reqs(self):
        ret = super().set_platform_bootloader_reqs()
        ret.append(PartSpec(mountpoint="/boot/efi", fstype="efi",
                            size=Size("200MiB"), max_size=Size("600MiB"),
                            grow=True))
        return ret


class MacEFI(EFI):
    _boot_stage1_format_types = ["macefi"]
    _boot_efi_description = N_("Apple EFI Boot Partition")
    _non_linux_format_types = ["macefi"]
    _packages = ["mactel-boot"]
    _boot_stage1_missing_error = N_("For a UEFI installation, you must include "
                                    "a Linux HFS+ ESP on a GPT-formatted "
                                    "disk, mounted at /boot/efi.")

    def set_platform_bootloader_reqs(self):
        ret = super().set_platform_bootloader_reqs()
        ret.append(PartSpec(mountpoint="/boot/efi", fstype="macefi",
                            size=Size("200MiB"), max_size=Size("600MiB"),
                            grow=True))
        return ret


class Aarch64EFI(EFI):
    _non_linux_format_types = ["vfat", "ntfs"]


class ArmEFI(EFI):
    _non_linux_format_types = ["vfat", "ntfs"]


class PPC(Platform):
    _ppc_machine = arch.get_ppc_machine()
    _boot_stage1_device_types = ["partition"]

    @property
    def ppc_machine(self):
        return self._ppc_machine


class IPSeriesPPC(PPC):
    _boot_stage1_format_types = ["prepboot"]
    _boot_stage1_max_end = Size("4 GiB")
    _boot_prep_description = N_("PReP Boot Partition")
    _boot_descriptions = {"partition": _boot_prep_description}
    _boot_stage1_missing_error = N_("You must include a PReP Boot Partition "
                                    "within the first 4GiB of an MBR- "
                                    "or GPT-formatted disk.")

    def set_platform_bootloader_reqs(self):
        ret = PPC.set_platform_bootloader_reqs(self)
        ret.append(PartSpec(fstype="prepboot", size=Size("4MiB")))
        return ret


class NewWorldPPC(PPC):
    _boot_stage1_format_types = ["appleboot"]
    _boot_apple_description = N_("Apple Bootstrap Partition")
    _boot_descriptions = {"partition": _boot_apple_description}
    _non_linux_format_types = ["hfs", "hfs+"]
    _boot_stage1_missing_error = N_("You must include an Apple Bootstrap "
                                    "Partition on an Apple Partition Map-"
                                    "formatted disk.")

    def set_platform_bootloader_reqs(self):
        ret = super().set_platform_bootloader_reqs()
        ret.append(PartSpec(fstype="appleboot", size=Size("1MiB")))
        return ret


class PowerNV(PPC):
    _boot_descriptions = {"partition": Platform._boot_partition_description}
    _boot_stage1_missing_error = N_("You must include at least one disk as an install target.")


class PS3(PPC):
    pass


class S390(Platform):
    _packages = ["s390utils"]
    _boot_stage1_device_types = ["disk", "partition"]
    _boot_dasd_description = N_("DASD")
    _boot_mbr_description = N_("Master Boot Record")
    _boot_zfcp_description = N_("zFCP")
    _boot_descriptions = {"dasd": _boot_dasd_description,
                          "zfcp": _boot_zfcp_description,
                          "disk": _boot_mbr_description,
                          "partition": Platform._boot_partition_description}
    _boot_stage1_missing_error = N_("You must include at least one MBR- or "
                                    "DASD-formatted disk as an install target.")

    def set_platform_boot_partition(self):
        """Return the default platform-specific partitioning information."""
        return [PartSpec(mountpoint="/boot", size=Size("1GiB"), lv=False)]


class ARM(Platform):
    _boot_stage1_device_types = ["disk"]
    _boot_mbr_description = N_("Master Boot Record")
    _boot_descriptions = {"disk": _boot_mbr_description,
                          "partition": Platform._boot_partition_description}

    _boot_stage1_missing_error = N_("You must include at least one MBR-formatted "
                                    "disk as an install target.")


def get_platform():
    """Check the architecture of the system and return an instance of a
       Platform subclass to match.  If the architecture could not be determined,
       raise an exception."""
    if arch.is_ppc():
        ppc_machine = arch.get_ppc_machine()

        if (ppc_machine == "PMac" and arch.get_ppc_mac_gen() == "NewWorld"):
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
