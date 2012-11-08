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
import os
import logging
log = logging.getLogger("anaconda")

import parted

from pyanaconda import bootloader
from pyanaconda.storage.devicelibs import mdraid
from pyanaconda.constants import DMI_CHASSIS_VENDOR

import iutil
from flags import flags

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)
N_ = lambda x: x

class Platform(object):
    """Platform

       A class containing platform-specific information and methods for use
       during installation.  The intent is to eventually encapsulate all the
       architecture quirks in one place to avoid lots of platform checks
       throughout anaconda."""
    _minimumSector = 0
    _packages = []

    bootloaderClass = bootloader.BootLoader
    # requirements for bootloader stage1 devices
    _boot_stage1_device_types = []
    _boot_stage1_format_types = []
    _boot_stage1_mountpoints = []
    _boot_stage1_max_end_mb = None
    _boot_stage1_raid_levels = []
    _boot_stage1_raid_metadata = []
    _boot_stage1_raid_member_types = []
    _boot_stage1_description = N_("bootloader device")
    _boot_raid_description = N_("RAID Device")
    _boot_partition_description = N_("First sector of boot partition")
    _boot_descriptions = {}

    _disklabel_types = []
    _non_linux_format_types = []

    def __init__(self):
        """Creates a new Platform object.  This is basically an abstract class.
           You should instead use one of the platform-specific classes as
           returned by getPlatform below.  Not all subclasses need to provide
           all the methods in this class."""

        if flags.gpt and "gpt" in self._disklabel_types:
            # move GPT to the top of the list
            self._disklabel_types.remove("gpt")
            self._disklabel_types.insert(0, "gpt")

    @property
    def diskLabelTypes(self):
        """A list of valid disklabel types for this architecture."""
        return self._disklabel_types

    @property
    def defaultDiskLabelType(self):
        """The default disklabel type for this architecture."""
        return self.diskLabelTypes[0]

    @property
    def bootStage1ConstraintDict(self):
        d = {"device_types": self._boot_stage1_device_types,
             "format_types": self._boot_stage1_format_types,
             "mountpoints": self._boot_stage1_mountpoints,
             "max_end_mb": self._boot_stage1_max_end_mb,
             "raid_levels": self._boot_stage1_raid_levels,
             "raid_metadata": self._boot_stage1_raid_metadata,
             "raid_member_types": self._boot_stage1_raid_member_types,
             "descriptions": self._boot_descriptions}
        return d

    def requiredDiskLabelType(self, device_type):
        return None

    def bestDiskLabelType(self, device):
        """The best disklabel type for the specified device."""
        if flags.testing:
            return self.defaultDiskLabelType

        # if there's a required type for this device type, use that
        labelType = self.requiredDiskLabelType(device.partedDevice.type)
        log.debug("required disklabel type for %s (%s) is %s"
                  % (device.name, device.partedDevice.type, labelType))
        if not labelType:
            # otherwise, use the first supported type for this platform
            # that is large enough to address the whole device
            labelType = self.defaultDiskLabelType
            log.debug("default disklabel type for %s is %s" % (device.name,
                                                               labelType))
            for lt in self.diskLabelTypes:
                l = parted.freshDisk(device=device.partedDevice, ty=lt)
                if l.maxPartitionStartSector > device.partedDevice.length:
                    labelType = lt
                    log.debug("selecting %s disklabel for %s based on size"
                              % (labelType, device.name))
                    break

        return labelType

    @property
    def minimumSector(self, disk):
        """Return the minimum starting sector for the provided disk."""
        return self._minimumSector

    @property
    def packages (self):
        _packages = self._packages
        if flags.cmdline.get('fips', None) == '1':
            _packages.append('dracut-fips')
        return _packages

    def setDefaultPartitioning(self):
        """Return the default platform-specific partitioning information."""
        from storage.partspec import PartSpec
        return [PartSpec(mountpoint="/boot",
                         size=500, weight=self.weight(mountpoint="/boot"))]

    def weight(self, fstype=None, mountpoint=None):
        """ Given an fstype (as a string) or a mountpoint, return an integer
            for the base sorting weight.  This is used to modify the sort
            algorithm for partition requests, mainly to make sure bootable
            partitions and /boot are placed where they need to be."""
        if mountpoint == "/boot":
            return 2000
        else:
            return 0

class X86(Platform):
    bootloaderClass = bootloader.GRUB2
    _boot_stage1_device_types = ["disk"]
    _boot_mbr_description = N_("Master Boot Record")
    _boot_descriptions = {"disk": _boot_mbr_description,
                          "partition": Platform._boot_partition_description,
                          "mdarray": Platform._boot_raid_description}


    _disklabel_types = ["msdos", "gpt"]
    # XXX hpfs, if reported by blkid/udev, will end up with a type of None
    _non_linux_format_types = ["vfat", "ntfs", "hpfs"]

    def __init__(self):
        super(X86, self).__init__()

    def setDefaultPartitioning(self):
        """Return the default platform-specific partitioning information."""
        from storage.partspec import PartSpec
        ret = Platform.setDefaultPartitioning(self)
        ret.append(PartSpec(fstype="biosboot", size=1,
                            weight=self.weight(fstype="biosboot")))
        return ret

    def weight(self, fstype=None, mountpoint=None):
        score = Platform.weight(self, fstype=fstype, mountpoint=mountpoint)
        if score:
            return score
        elif fstype == "biosboot":
            return 5000
        else:
            return 0

class EFI(Platform):
    bootloaderClass = bootloader.EFIGRUB

    _boot_stage1_format_types = ["efi"]
    _boot_stage1_device_types = ["partition"]
    _boot_stage1_mountpoints = ["/boot/efi"]
    _boot_efi_description = N_("EFI System Partition")
    _boot_descriptions = {"partition": _boot_efi_description,
                          "mdarray": Platform._boot_raid_description}

    _disklabel_types = ["gpt"]
    # XXX hpfs, if reported by blkid/udev, will end up with a type of None
    _non_linux_format_types = ["vfat", "ntfs", "hpfs"]

    def setDefaultPartitioning(self):
        from storage.partspec import PartSpec
        ret = Platform.setDefaultPartitioning(self)
        ret.append(PartSpec(mountpoint="/boot/efi", fstype="efi", size=20,
                            maxSize=200,
                            grow=True, weight=self.weight(fstype="efi")))
        return ret

    def weight(self, fstype=None, mountpoint=None):
        score = Platform.weight(self, fstype=fstype, mountpoint=mountpoint)
        if score:
            return score
        elif fstype == "efi" or mountpoint == "/boot/efi":
            return 5000
        else:
            return 0

class MacEFI(EFI):
    bootloaderClass = bootloader.MacEFIGRUB

    _boot_stage1_format_types = ["hfs+"]
    _boot_efi_description = N_("Apple EFI Boot Partition")
    _non_linux_format_types = ["hfs+"]
    _packages = ["mactel-boot"]

    def setDefaultPartitioning(self):
        from storage.partspec import PartSpec
        ret = Platform.setDefaultPartitioning(self)
        ret.append(PartSpec(mountpoint="/boot/efi", fstype="hfs+", size=20,
                            maxSize=200,
                            grow=True, weight=self.weight(mountpoint="/boot/efi")))
        return ret

class PPC(Platform):
    _ppcMachine = iutil.getPPCMachine()
    bootloaderClass = bootloader.GRUB2
    _boot_stage1_device_types = ["partition"]

    @property
    def ppcMachine(self):
        return self._ppcMachine

class IPSeriesPPC(PPC):
    bootloaderClass = bootloader.IPSeriesGRUB2
    _boot_stage1_format_types = ["prepboot"]
    _boot_stage1_max_end_mb = 10
    _boot_prep_description = N_("PReP Boot Partition")
    _boot_descriptions = {"partition": _boot_prep_description}
    _disklabel_types = ["msdos"]

    def setDefaultPartitioning(self):
        from storage.partspec import PartSpec
        ret = PPC.setDefaultPartitioning(self)
        ret.append(PartSpec(fstype="prepboot", size=4,
                            weight=self.weight(fstype="prepboot")))
        return ret

    def weight(self, fstype=None, mountpoint=None):
        score = Platform.weight(self, fstype=fstype, mountpoint=mountpoint)
        if score:
            return score
        elif fstype == "prepboot":
            return 5000
        else:
            return 0

class NewWorldPPC(PPC):
    bootloaderClass = bootloader.MacYaboot
    _boot_stage1_format_types = ["appleboot"]
    _boot_apple_description = N_("Apple Bootstrap Partition")
    _boot_descriptions = {"partition": _boot_apple_description}
    _disklabel_types = ["mac"]
    _non_linux_format_types = ["hfs", "hfs+"]

    def setDefaultPartitioning(self):
        from storage.partspec import PartSpec
        ret = Platform.setDefaultPartitioning(self)
        ret.append(PartSpec(fstype="appleboot", size=1, maxSize=1,
                            weight=self.weight(fstype="appleboot")))
        return ret

    def weight(self, fstype=None, mountpoint=None):
        score = Platform.weight(self, fstype=fstype, mountpoint=mountpoint)
        if score:
            return score
        elif fstype == "appleboot":
            return 5000
        else:
            return 0

class PS3(PPC):
    pass

class S390(Platform):
    bootloaderClass = bootloader.ZIPL
    _packages = ["s390utils"]
    _disklabel_types = ["msdos", "dasd"]
    _boot_stage1_device_types = ["disk", "partition"]
    _boot_dasd_description = N_("DASD")
    _boot_zfcp_description = N_("zFCP")
    _boot_descriptions = {"dasd": _boot_dasd_description,
                          "zfcp": _boot_zfcp_description,
                          "partition": Platform._boot_partition_description}

    def __init__(self):
        Platform.__init__(self)

    def setDefaultPartitioning(self):
        """Return the default platform-specific partitioning information."""
        from storage.partspec import PartSpec
        return [PartSpec(mountpoint="/boot", size=500,
                         weight=self.weight(mountpoint="/boot"), lv=True,
                         singlePV=True)]

    def requiredDiskLabelType(self, device_type):
        """The required disklabel type for the specified device type."""
        if device_type == parted.DEVICE_DASD:
            return "dasd"

        return super(S390, self).requiredDiskLabelType(device_type)

class Sparc(Platform):
    bootloaderClass = bootloader.SILO
    _boot_stage1_format_types = []
    _boot_stage1_mountpoints = []
    _boot_stage1_max_end_mb = None
    _disklabel_types = ["sun"]

    @property
    def minimumSector(self, disk):
        (cylinders, heads, sectors) = disk.device.biosGeometry
        start = long(sectors * heads)
        start /= long(1024 / disk.device.sectorSize)
        return start+1

class ARM(Platform):
    _armMachine = None
    bootloaderClass = bootloader.UBOOT
    _boot_stage1_device_types = ["disk"]
    _boot_mbr_description = N_("Master Boot Record")
    _boot_descriptions = {"disk": _boot_mbr_description,
                          "partition": Platform._boot_partition_description}

    _disklabel_types = ["msdos"]

    @property
    def armMachine(self):
        if not self._armMachine:
            self._armMachine = iutil.getARMMachine()
        return self._armMachine

    def weight(self, fstype=None, mountpoint=None):
        """Return the ARM platform-specific weight for the / partition.
           On ARM images '/' must be the last partition, so we try to
           weight it accordingly."""
        if mountpoint == "/":
            return -100
        else:
            return Platform.weight(self, fstype=fstype, mountpoint=mountpoint)

class omapARM(ARM):
    _boot_stage1_format_types = ["vfat"]
    _boot_stage1_device_types = ["partition"]
    _boot_stage1_mountpoints = ["/boot/uboot"]
    _boot_uboot_description = N_("U-Boot Partition")
    _boot_descriptions = {"partition": _boot_uboot_description}

    def setDefaultPartitioning(self):
        """Return the ARM-OMAP platform-specific partitioning information."""
        from storage.partspec import PartSpec
        ret = [PartSpec(mountpoint="/boot/uboot", fstype="vfat",
                        size=20, maxSize=200, grow=True,
                        weight=self.weight(fstype="vfat", mountpoint="/boot/uboot"))]
        ret.append(PartSpec(mountpoint="/", fstype="ext4",
                            size=2000, maxSize=3000,
                            weight=self.weight(mountpoint="/")))
        return ret

    def weight(self, fstype=None, mountpoint=None):
        """Return the ARM-OMAP platform-specific weights for the uboot
           and / partitions.  On OMAP, uboot must be the first partition,
           and '/' must be the last partition, so we try to weight them
           accordingly."""
        if fstype == "vfat" and mountpoint == "/boot/uboot":
            return 6000
        elif mountpoint == "/":
            return -100
        else:
            return Platform.weight(self, fstype=fstype, mountpoint=mountpoint)

def getPlatform():
    """Check the architecture of the system and return an instance of a
       Platform subclass to match.  If the architecture could not be determined,
       raise an exception."""
    if iutil.isPPC():
        ppcMachine = iutil.getPPCMachine()

        if (ppcMachine == "PMac" and iutil.getPPCMacGen() == "NewWorld"):
            return NewWorldPPC()
        elif ppcMachine in ["iSeries", "pSeries"]:
            return IPSeriesPPC()
        elif ppcMachine == "PS3":
            return PS3()
        else:
            raise SystemError, "Unsupported PPC machine type: %s" % ppcMachine
    elif iutil.isS390():
        return S390()
    elif iutil.isSparc():
        return Sparc()
    elif iutil.isEfi():
        if iutil.isMactel():
            return MacEFI()
        else:
            return EFI()
    elif iutil.isX86():
        return X86()
    elif iutil.isARM():
        armMachine = iutil.getARMMachine()
        if armMachine == "omap":
            return omapARM()
        else:
            return ARM()
    else:
        raise SystemError, "Could not determine system architecture."
