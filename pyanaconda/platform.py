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

import parted

from pyanaconda import bootloader
from pyanaconda.storage.devicelibs import mdraid

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

    _bootloaderClass = bootloader.BootLoader
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

    def __init__(self, anaconda):
        """Creates a new Platform object.  This is basically an abstract class.
           You should instead use one of the platform-specific classes as
           returned by getPlatform below.  Not all subclasses need to provide
           all the methods in this class."""
        self.anaconda = anaconda

        if flags.nogpt and "gpt" in self._disklabel_types and \
           len(self._disklabel_types) > 1:
            self._disklabel_types.remove("gpt")

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
                         fstype=self.anaconda.storage.defaultBootFSType,
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
    _bootloaderClass = bootloader.GRUB2
    _boot_stage1_device_types = ["disk"]
    _boot_mbr_description = N_("Master Boot Record")
    _boot_descriptions = {"disk": _boot_mbr_description,
                          "partition": Platform._boot_partition_description,
                          "mdarray": Platform._boot_raid_description}


    _disklabel_types = ["gpt", "msdos"]
    # XXX hpfs, if reported by blkid/udev, will end up with a type of None
    _non_linux_format_types = ["vfat", "ntfs", "hpfs"]

    def __init__(self, anaconda):
        super(X86, self).__init__(anaconda)
        self.blackListGPT()

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

    def blackListGPT(self):
        buf = iutil.execWithCapture("dmidecode",
                                    ["-s", "chassis-manufacturer"],
                                    stderr="/dev/tty5")
        if "LENOVO" in buf.splitlines() and "gpt" in self._disklabel_types:
            self._disklabel_types.remove("gpt")

class EFI(Platform):
    _bootloaderClass = bootloader.EFIGRUB

    _boot_stage1_format_types = ["efi"]
    _boot_stage1_device_types = ["partition", "mdarray"]
    _boot_stage1_raid_levels = [mdraid.RAID1]
    _boot_stage1_raid_metadata = ["1.0"]
    _boot_stage1_raid_member_types = ["partition"]
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

class PPC(Platform):
    _ppcMachine = iutil.getPPCMachine()
    _bootloaderClass = bootloader.Yaboot
    _boot_stage1_device_types = ["partition"]

    @property
    def ppcMachine(self):
        return self._ppcMachine

class IPSeriesPPC(PPC):
    _bootloaderClass = bootloader.IPSeriesYaboot
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
    _bootloaderClass = bootloader.MacYaboot
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
    _bootloaderClass = bootloader.ZIPL
    _packages = ["s390utils"]
    _disklabel_types = ["msdos", "dasd"]
    _boot_stage1_device_types = ["disk", "partition"]

    def __init__(self, anaconda):
        Platform.__init__(self, anaconda)

    def setDefaultPartitioning(self):
        """Return the default platform-specific partitioning information."""
        from storage.partspec import PartSpec
        return [PartSpec(mountpoint="/boot", size=500,
                         fstype=self.anaconda.storage.defaultBootFSType,
                         weight=self.weight(mountpoint="/boot"), asVol=True,
                         singlePV=True)]

    def requiredDiskLabelType(self, device_type):
        """The required disklabel type for the specified device type."""
        if device_type == "dasd":
            return "dasd"

        return super(S390, self).requiredDiskLabelType(device_type)

class Sparc(Platform):
    _bootloaderClass = bootloader.SILO
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

def getPlatform(anaconda):
    """Check the architecture of the system and return an instance of a
       Platform subclass to match.  If the architecture could not be determined,
       raise an exception."""
    if iutil.isPPC():
        ppcMachine = iutil.getPPCMachine()

        if (ppcMachine == "PMac" and iutil.getPPCMacGen() == "NewWorld"):
            return NewWorldPPC(anaconda)
        elif ppcMachine in ["iSeries", "pSeries"]:
            return IPSeriesPPC(anaconda)
        elif ppcMachine == "PS3":
            return PS3(anaconda)
        else:
            raise SystemError, "Unsupported PPC machine type"
    elif iutil.isS390():
        return S390(anaconda)
    elif iutil.isSparc():
        return Sparc(anaconda)
    elif iutil.isEfi():
        return EFI(anaconda)
    elif iutil.isX86():
        return X86(anaconda)
    else:
        raise SystemError, "Could not determine system architecture."
