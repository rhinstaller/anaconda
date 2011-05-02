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

import iutil
from flags import flags

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

class Platform(object):
    """Platform

       A class containing platform-specific information and methods for use
       during installation.  The intent is to eventually encapsulate all the
       architecture quirks in one place to avoid lots of platform checks
       throughout anaconda."""
    _minimumSector = 0
    _packages = []
    _bootloaderClass = bootloader.BootLoader

    def __init__(self, anaconda):
        """Creates a new Platform object.  This is basically an abstract class.
           You should instead use one of the platform-specific classes as
           returned by getPlatform below.  Not all subclasses need to provide
           all the methods in this class."""
        self.anaconda = anaconda
        self.bootloader = self._bootloaderClass(storage=getattr(anaconda,
                                                                "storage",
                                                                None))

    @property
    def bootDevice(self):
        """The device that includes the /boot filesystem."""
        return self.bootloader.stage2_device

    @property
    def bootLoaderDevice(self):
        """The device the bootloader will be installed into."""
        return self.bootloader.stage1_device

    @property
    def bootFSTypes(self):
        """A list of all valid filesystem types for the boot partition."""
        return self.bootloader.stage2_format_types

    @property
    def defaultBootFSType(self):
        """The default filesystem type for the boot partition."""
        return self.bootFSTypes[0]

    @property
    def diskLabelTypes(self):
        """A list of valid disklabel types for this architecture."""
        return self.bootloader.disklabel_types

    @property
    def defaultDiskLabelType(self):
        """The default disklabel type for this architecture."""
        return self.diskLabelTypes[0]

    def requiredDiskLabelType(self, device_type):
        return None

    def bestDiskLabelType(self, device):
        """The best disklabel type for the specified device."""
        # if there's a required type for this device type, use that
        labelType = self.requiredDiskLabelType(device.partedDevice.type)
        if not labelType:
            # otherwise, use the first supported type for this platform
            # that is large enough to address the whole device
            labelType = self.defaultDiskLabelType
            for lt in self.diskLabelTypes:
                l = parted.freshDisk(device=device.partedDevice, ty=lt)
                if l.maxPartitionStartSector < device.partedDevice.length:
                    labelType = lt
                    break

        return labelType

    def checkBootRequest(self):
        """Perform an architecture-specific check on the boot device.  Not all
           platforms may need to do any checks.  Returns a list of errors if
           there is a problem, or [] otherwise."""
        req = self.bootDevice
        if not req:
            return ([_("You have not created a bootable partition.")], [])

        self.bootloader.is_valid_stage2_device(req)
        errors = self.bootloader.errors
        warnings = self.bootloader.warnings
        return (errors, warnings)

    def checkBootLoaderRequest(self):
        """ Perform architecture-specific checks on the bootloader device.

            Returns a list of error strings.
        """
        req = self.bootLoaderDevice
        if not req:
            return ([_("you have not created a bootloader stage1 target device")], [])

        self.bootloader.is_valid_stage1_device(req)
        errors = self.bootloader.errors
        warnings = self.bootloader.warnings
        return (errors, warnings)

    @property
    def minimumSector(self, disk):
        """Return the minimum starting sector for the provided disk."""
        return self._minimumSector

    @property
    def packages (self):
        _packages = self._packages + self.bootloader.packages
        if flags.cmdline.get('fips', None) == '1':
            _packages.append('dracut-fips')
        return _packages

    def setDefaultPartitioning(self):
        """Return the default platform-specific partitioning information."""
        from storage.partspec import PartSpec
        return [PartSpec(mountpoint="/boot", fstype=self.defaultBootFSType, size=500,
                         weight=self.weight(mountpoint="/boot"))]

    def weight(self, fstype=None, mountpoint=None):
        """ Given an fstype (as a string) or a mountpoint, return an integer
            for the base sorting weight.  This is used to modify the sort
            algorithm for partition requests, mainly to make sure bootable
            partitions and /boot are placed where they need to be."""
        if fstype in self.bootFSTypes and mountpoint == "/boot":
            return 2000
        else:
            return 0

class X86(Platform):
    _bootloaderClass = bootloader.GRUB2

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
    _bootloaderClass = bootloader.EFIGRUB

    def setDefaultPartitioning(self):
        from storage.partspec import PartSpec
        ret = Platform.setDefaultPartitioning(self)
        ret.append(PartSpec(mountpoint="/boot/efi", fstype="efi", size=20,
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

    @property
    def ppcMachine(self):
        return self._ppcMachine

class IPSeriesPPC(PPC):
    _bootloaderClass = bootloader.IPSeriesYaboot

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

    def __init__(self, anaconda):
        Platform.__init__(self, anaconda)

    def setDefaultPartitioning(self):
        """Return the default platform-specific partitioning information."""
        from storage.partspec import PartSpec
        return [PartSpec(mountpoint="/boot", fstype=self.defaultBootFSType, size=500,
                         weight=self.weight(mountpoint="/boot"), asVol=True,
                         singlePV=True)]

    def requiredDiskLabelType(self, device_type):
        """The required disklabel type for the specified device type."""
        if device_type == "dasd":
            return "dasd"

        return super(S390, self).requiredDiskLabelType(device_type)

class Sparc(Platform):
    _bootloaderClass = bootloader.SILO

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
