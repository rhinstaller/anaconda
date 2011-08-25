# bootloader.py
# Anaconda's bootloader configuration module.
#
# Copyright (C) 2011 Red Hat, Inc.
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
# Red Hat Author(s): David Lehman <dlehman@redhat.com>
#

import sys
import os
import re
import struct

from pyanaconda import iutil
from pyanaconda.storage.devicelibs import mdraid
from pyanaconda.isys import sync
from pyanaconda.product import productName
from pyanaconda.flags import flags
from pyanaconda.constants import *
from pyanaconda.storage.errors import StorageError

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)
N_ = lambda x: x

import logging
log = logging.getLogger("storage")


def get_boot_block(device, seek_blocks=0):
    status = device.status
    if not status:
        try:
            device.setup()
        except StorageError:
            return ""
    block_size = device.partedDevice.sectorSize
    fd = os.open(device.path, os.O_RDONLY)
    if seek_blocks:
        os.lseek(fd, seek_blocks * block_size, 0)
    block = os.read(fd, 512)
    os.close(fd)
    if not status:
        try:
            device.teardown(recursive=True)
        except StorageError:
            pass

    return block

def is_windows_boot_block(block):
    try:
        windows = (len(block) >= 512 and
                   struct.unpack("H", block[0x1fe: 0x200]) == (0xaa55,))
    except struct.error:
        windows = False
    return windows

def has_windows_boot_block(device):
    return is_windows_boot_block(get_boot_block(device))


class BootLoaderError(Exception):
    pass


class Arguments(set):
    def __str__(self):
        return " ".join(self)

class BootLoaderImage(object):
    """ Base class for bootloader images. Suitable for non-linux OS images. """
    def __init__(self, device=None, label=None, short=None):
        self.label = label
        self.short_label = short
        self.device = device


class LinuxBootLoaderImage(BootLoaderImage):
    def __init__(self, device=None, label=None, short=None, version=None):
        super(LinuxBootLoaderImage, self).__init__(device=device, label=label)
        self.label = label              # label string
        self.short_label = short        # shorter label string
        self.device = device            # StorageDevice instance
        self.version = version          # kernel version string
        self._kernel = None             # filename string
        self._initrd = None             # filename string

    @property
    def kernel(self):
        filename = self._kernel
        if self.version and not filename:
            filename = "vmlinuz-%s" % self.version
        return filename

    @property
    def initrd(self):
        filename = self._initrd
        if self.version and not filename:
            filename = "initramfs-%s.img" % self.version
        return filename

class TbootLinuxBootLoaderImage(LinuxBootLoaderImage):
    _multiboot = "tboot.gz"     # filename string
    _mbargs = ["logging=vga,serial,memory"]
    _args = ["intel_iommu=on"]

    def __init__(self, device=None, label=None, short=None, version=None):
        super(TbootLinuxBootLoaderImage, self).__init__(
                                                   device=device, label=label,
                                                   short=short, version=version)

    @property
    def multiboot(self):
        return self._multiboot

    @property
    def mbargs(self):
        return self._mbargs

    @property
    def args(self):
        return self._args

class BootLoader(object):
    """TODO:
            - iSeries bootloader?
                - same as pSeries, except optional, I think
            - upgrade of non-grub bootloaders
            - detection of existing bootloaders
            - improve password encryption for grub
                - fix handling of kickstart-provided already-encrypted
                  password
    """
    name = "Generic Bootloader"
    packages = []
    config_file = None
    config_file_mode = 0600
    can_dual_boot = False
    can_update = False
    image_label_attr = "label"

    encryption_support = False

    stage2_is_valid_stage1 = False

    # requirements for stage2 devices
    stage2_device_types = []
    stage2_raid_levels = []
    stage2_raid_metadata = []
    stage2_raid_member_types = []
    stage2_format_types = ["ext4", "ext3", "ext2"]
    stage2_mountpoints = ["/boot", "/"]
    stage2_bootable = False
    stage2_description = N_("/boot filesystem")
    stage2_max_end_mb = 2 * 1024 * 1024

    # this is so stupid...
    global_preserve_args = ["speakup_synth", "apic", "noapic", "apm", "ide",
                            "noht", "acpi", "video", "pci", "nodmraid",
                            "nompath", "nomodeset", "noiswmd", "fips"]
    preserve_args = []

    _trusted_boot = False

    def __init__(self, storage=None):
        # pyanaconda.storage.Storage instance
        self.storage = storage

        self.boot_args = Arguments()
        self.dracut_args = Arguments()

        self._drives = []
        self._drive_order = []

        # timeout in seconds
        self._timeout = None
        self.password = None

        # console/serial stuff
        self.console = ""
        self.console_options = ""
        self._set_console()

        # list of BootLoaderImage instances representing bootable OSs
        self.linux_images = []
        self.chain_images = []

        # default image
        self._default_image = None

        # the device the bootloader will be installed on
        self._stage1_device = None

        # the "boot drive", meaning the drive we prefer stage1 be on
        self.stage1_drive = None

        self._update_only = False

        self.stage2_is_preferred_stage1 = False

        self.errors = []
        self.warnings = []

    #
    # stage1 device access
    #
    # pylint: disable-msg=E0202
    @property
    def stage1_device(self):
        """ Stage1 target device. """
        if not self._stage1_device:
            log.debug("no stage1 device: %s"
                      % [d.name for d in self.stage1_devices])
            if self.stage2_is_preferred_stage1:
                log.debug("using stage2 device as stage1")
                self.stage1_device = self.stage2_device
            else:
                try:
                    self.stage1_device = self.stage1_devices[0]
                except IndexError:
                    pass

        return self._stage1_device

    # pylint: disable-msg=E0102,E0202,E1101
    @stage1_device.setter
    def stage1_device(self, device):
        log.debug("new bootloader stage1 device: %s" % getattr(device,
                                                               "name", None))
        self._stage1_device = device
        if device:
            self.stage1_drive = device.disks[0]

    # pylint: disable-msg=E0202
    @property
    def stage2_device(self):
        """ Stage2 target device. """
        return self.storage.mountpoints.get("/boot", self.storage.rootDevice)

    #
    # drive list access
    #
    # pylint: disable-msg=E0202
    @property
    def drive_order(self):
        """Potentially partial order for drives."""
        return self._drive_order

    # pylint: disable-msg=E0102,E0202,E1101
    @drive_order.setter
    def drive_order(self, order):
        log.debug("new drive order: %s" % order)
        self._drive_order = order
        self.clear_drive_list() # this will get regenerated on next access

    def _sort_drives(self, drives):
        """Sort drives based on the drive order."""
        _drives = drives[:]
        for name in reversed(self._drive_order):
            try:
                idx = [d.name for d in _drives].index(name)
            except ValueError:
                log.error("bios order specified unknown drive %s" % name)
                continue

            first = _drives.pop(idx)
            _drives.insert(0, first)

        return _drives

    def clear_drive_list(self):
        """ Clear the drive list to force re-populate on next access. """
        self._drives = []

    @property
    def drives(self):
        """Sorted list of available drives."""
        if self._drives:
            # only generate the list if it is empty
            return self._drives

        # XXX requiring partitioned may break clearpart
        drives = [d for d in self.storage.disks if d.partitioned]
        self._drives = self._sort_drives(drives)

        # set "boot drive"
        self.stage1_drive = self._drives[0]

        return self._drives

    #
    # image list access
    #
    # pylint: disable-msg=E0202
    @property
    def default(self):
        """The default image."""
        if not self._default_image:
            if self.linux_images:
                _default = self.linux_images[0]
            else:
                _default = LinuxBootLoaderImage(device=self.storage.rootDevice,
                                                label=productName,
                                                short="linux")

            self._default_image = _default

        return self._default_image

    # pylint: disable-msg=E0102,E0202,E1101
    @default.setter
    def default(self, image):
        if image not in self.images:
            raise ValueError("new default image not in image list")

        log.debug("new default image: %s" % image)
        self._default_image = image

    @property
    def images(self):
        """ List of OS images that will be included in the configuration. """
        if not self.linux_images:
            self.linux_images.append(self.default)

        all_images = self.linux_images
        all_images.extend([i for i in self.chain_images if i.label])
        return all_images

    def clear_images(self):
        """Empty out the image list."""
        self.linux_images = []
        self.chain_images = []

    def add_image(self, image):
        """Add a BootLoaderImage instance to the image list."""
        if isinstance(image, LinuxBootLoaderImage):
            self.linux_images.append(image)
        else:
            self.chain_images.append(image)

    def image_label(self, image):
        """Return the appropriate image label for this bootloader."""
        return getattr(image, self.image_label_attr)

    def _find_chain_images(self):
        """ Collect a list of potential non-linux OS installations. """
        # XXX not used -- do we want to pre-populate the image list for the ui?
        self.chain_images = []
        if not self.can_dual_boot:
            return

        for device in [d for d in self.bootable_chain_devices if d.exists]:
            self.chain_images.append(BootLoaderImage(device=device))

    #
    # platform-specific data access
    #
    @property
    def platform(self):
        return self.storage.platform

    @property
    def disklabel_types(self):
        return self.platform._disklabel_types

    @property
    def device_descriptions(self):
        return self.platform.bootStage1ConstraintDict["descriptions"]

    #
    # constraint checking for target devices
    #
    def _is_valid_md(self, device, device_types=None, raid_levels=None,
                     metadata=None, member_types=None, desc=""):
        ret = True
        if device.type != "mdarray":
            return ret

        if raid_levels and device.level not in raid_levels:
            levels_str = ",".join("RAID%d" % l for l in raid_levels)
            self.errors.append(_("RAID sets that contain '%s' must have one "
                                 "of the following raid levels: %s.")
                               % (desc, levels_str))
            ret = False

        if metadata and device.metadataVersion not in metadata:
            self.errors.append(_("RAID sets that contain '%s' must have one "
                                 "of the following metadata versions: %s.")
                               % (desc, ",".join(metadata)))
            ret = False

        if member_types:
            for member in device.devices:
                if not self._device_type_match(member, member_types):
                    self.errors.append(_("RAID sets that contain '%s' must "
                                         "have one of the following device "
                                         "types: %s.")
                                       % (desc, ",".join(member_types)))
                    ret = False

        log.debug("_is_valid_md(%s) returning %s" % (device.name,ret))
        return ret

    def _is_valid_disklabel(self, device, disklabel_types=None, desc=""):
        ret = True
        if self.disklabel_types:
            for disk in device.disks:
                label_type = getattr(disk.format, "labelType", None)
                if not label_type or label_type not in self.disklabel_types:
                    types_str = ",".join(disklabel_types)
                    self.errors.append(_("%s must have one of the following "
                                         "disklabel types: %s.")
                                       % (device.name, types_str))
                    ret = False

        log.debug("_is_valid_disklabel(%s) returning %s" % (device.name,ret))
        return ret

    def _is_valid_format(self, device, format_types=None, mountpoints=None,
                         desc=""):
        ret = True
        if format_types and device.format.type not in format_types:
            self.errors.append(_("%s cannot be of type %s.")
                               % (desc, device.format.type))
            ret = False

        log.debug("_is_valid_format(%s) returning %s" % (device.name,ret))
        return ret

    def _is_valid_size(self, device, desc=""):
        ret = True
        msg = None
        errors = []
        if device.format.minSize and device.format.maxSize:
            msg = (_("%s must be between %d and %d MB in size")
                   % (desc, device.format.minSize, device.format.maxSize))

        if device.format.minSize and device.size < device.format.minSize:
            if msg is None:
                errors.append(_("%s must not be smaller than %dMB.")
                              % (desc, device.format.minSize))
            else:
                errors.append(msg)

            ret = False

        if device.format.maxSize and device.size > device.format.maxSize:
            if msg is None:
                errors.append(_("%s must not be larger than %dMB.")
                              % (desc, device.format.maxSize))
            elif msg not in errors:
                # don't add the same error string twice
                errors.append(msg)

            ret = False

        log.debug("_is_valid_size(%s) returning %s" % (device.name,ret))
        return ret

    def _is_valid_location(self, device, max_mb=None, desc=""):
        ret = True
        if max_mb and device.type == "partition":
            end_sector = device.partedPartition.geometry.end
            sector_size = device.partedPartition.disk.device.sectorSize
            end_mb = (sector_size * end_sector) / (1024.0 * 1024.0)
            if end_mb > max_mb:
                self.errors.append(_("%s must be within the first %dMB of "
                                     "the disk.") % (desc, max_mb))
                ret = False

        log.debug("_is_valid_location(%s) returning %s" % (device.name,ret))
        return ret

    #
    # target/stage1 device access
    #
    def _device_type_index(self, device, types):
        """ Return the index of the matching type in types to device's type.

            Return None if no match is found. """
        index = None
        try:
            index = types.index(device.type)
        except ValueError:
            if "disk" in types and device.isDisk:
                index = types.index("disk")

        return index

    def _device_type_match(self, device, types):
        """ Return True if device is of one of the types in the list types. """
        return self._device_type_index(device, types) is not None

    def device_description(self, device):
        device_types = self.device_descriptions.keys()
        idx = self._device_type_index(device, device_types)
        if idx is None:
            raise ValueError("No description available for %s" % device.type)

        # this looks unnecessarily complicated, but it handles the various
        # device types that we treat as disks
        return self.device_descriptions[device_types[idx]]

    def set_preferred_stage1_type(self, preferred):
        """ Set a preferred type of stage1 device. """
        if not self.stage2_is_valid_stage1:
            # "partition" means first sector of stage2 and is only meaningful
            # for bootloaders that can use stage2 as stage1
            return

        if preferred == "mbr":
            # "mbr" is already the default
            return

        # partition means "use the stage2 device for a stage1 device"
        self.stage2_is_preferred_stage1 = True

    def is_valid_stage1_device(self, device):
        """ Return True if the device is a valid stage1 target device.

            Also collect lists of errors and warnings.

            The criteria for being a valid stage1 target device vary from
            platform to platform. On some platforms a disk with an msdos
            disklabel is a valid stage1 target, while some platforms require
            a special device. Some examples of these special devices are EFI
            system partitions on EFI machines, PReP boot partitions on
            iSeries, and Apple bootstrap partitions on Mac. """
        self.errors = []
        self.warnings = []
        valid = True

        if device is None:
            return False

        description = self.device_description(device)
        constraint = self.platform.bootStage1ConstraintDict

        if self.stage2_is_valid_stage1 and device == self.stage2_device:
            # special case
            valid = self.is_valid_stage2_device(device)

            # we'll be checking stage2 separately so don't duplicate messages
            self.problems = []
            self.warnings = []
            return valid

        if os.path.exists("/dev/live") and \
           os.path.realpath("/dev/live") == device.path:
            self.errors.append(_("%s cannot be on the live device.")
                               % description)
            valid = False

        if not self._device_type_match(device, constraint["device_types"]):
            self.errors.append(_("%s cannot be of type %s.")
                               % (description, device.type))
            valid = False

        if not self._is_valid_disklabel(device,
                                        disklabel_types=self.disklabel_types,
                                        desc=description):
            valid = False

        if not self._is_valid_size(device, desc=description):
            valid = False

        if not self._is_valid_location(device,
                                       max_mb=constraint["max_end_mb"],
                                       desc=description):
            valid = False

        if not self._is_valid_md(device,
                                 device_types=constraint["device_types"],
                                 raid_levels=constraint["raid_levels"],
                                 metadata=constraint["raid_metadata"],
                                 member_types=constraint["raid_member_types"],
                                 desc=description):
            valid = False

        if not self.stage2_bootable and not getattr(device, "bootable", True):
            log.warning("%s not bootable" % device.name)

        # XXX does this need to be here?
        if getattr(device.format, "label", None) in ("ANACONDA", "LIVE"):
            log.info("ignoring anaconda boot disk")
            valid = False

        if not self._is_valid_format(device,
                                     format_types=constraint["format_types"],
                                     mountpoints=constraint["mountpoints"],
                                     desc=description):
            valid = False

        if not self.encryption_support and device.encrypted:
            self.errors.append(_("%s cannot be on an encrypted block "
                                 "device.") % description)
            valid = False

        log.debug("is_valid_stage1_device(%s) returning %s" % (device.name,
                                                                valid))
        return valid

    @property
    def stage1_devices(self):
        """ A list of valid stage1 target devices.

            The list self.stage1_device_types is ordered, so we return a list
            of all valid target devices, sorted by device type, then sorted
            according to our drive ordering.
        """
        device_types = self.platform.bootStage1ConstraintDict["device_types"]
        slots = [[] for t in device_types]
        for device in self.storage.devices:
            idx = self._device_type_index(device, device_types)
            if idx is None:
                continue

            if self.is_valid_stage1_device(device):
                slots[idx].append(device)

        devices = []
        for slot in slots:
            devices.extend(slot)

        devices = self._sort_drives(devices)

        # if a boot drive has been chosen put it, and devices on it, first
        # XXX should this be done in _sort_drives instead?
        if self.stage1_drive:
            boot_devs = [d for d in devices if self.stage1_drive in d.disks]
            if len(boot_devs) != len(devices):
                for dev in reversed(boot_devs):
                    idx = devices.index(dev)
                    devices.insert(0, devices.pop(idx))

        return devices

    #
    # boot/stage2 device access
    #

    def is_valid_stage2_device(self, device, linux=True, non_linux=False):
        """ Return True if the device is suitable as a stage2 target device.

            Also collect lists of errors and warnings.
        """
        self.errors = []
        self.warnings = []
        valid = True

        if device is None:
            return False

        if not self._device_type_match(device, self.stage2_device_types):
            self.errors.append(_("%s cannot be of type %s")
                               % (self.stage2_description, device.type))
            valid = False

        if not self._is_valid_disklabel(device,
                                        disklabel_types=self.disklabel_types,
                                        desc=self.stage2_description):
            valid = False

        if not self._is_valid_size(device, desc=self.stage2_description):
            valid = False

        if not self._is_valid_location(device,
                                       max_mb=self.stage2_max_end_mb,
                                       desc=self.stage2_description):
            valid = False

        if not self._is_valid_md(device, device_types=self.stage2_device_types,
                                 raid_levels=self.stage2_raid_levels,
                                 metadata=self.stage2_raid_metadata,
                                 member_types=self.stage2_raid_member_types,
                                 desc=self.stage2_description):
            valid = False

        if linux and \
           not self._is_valid_format(device,
                                     format_types=self.stage2_format_types,
                                     mountpoints=self.stage2_mountpoints,
                                     desc=self.stage2_description):
            valid = False

        non_linux_format_types = self.platform._non_linux_format_types
        if non_linux and \
           not self._is_valid_format(device,
                                     format_types=non_linux_format_types):
            valid = False

        if not self.encryption_support and device.encrypted:
            self.errors.append(_("%s cannot be on an encrypted block "
                                 "device.") % self.stage2_description)
            valid = False

        log.debug("is_valid_stage2_device(%s) returning %s" % (device.name,
                                                                valid))
        return valid

    @property
    def bootable_chain_devices(self):
        """ Potential boot devices containing non-linux operating systems. """
        # make sure we don't clobber error/warning lists
        errors = self.errors[:]
        warnings = self.warnings[:]
        ret = [d for d in self.storage.devices
                if self.is_valid_stage2_device(d, linux=False, non_linux=True)]
        self.errors = errors
        self.warnings = warnings
        return ret

    @property
    def bootable_devices(self):
        """ Potential boot devices containing linux operating systems. """
        # make sure we don't clobber error/warning lists
        errors = self.errors[:]
        warnings = self.warnings[:]
        ret = [d for d in self.storage.devices
                    if self.is_valid_stage2_device(d)]
        self.errors = errors
        self.warnings = warnings
        return ret

    #
    # miscellaneous
    #

    @property
    def has_windows(self):
        return False

    # pylint: disable-msg=E0202
    @property
    def timeout(self):
        """Bootloader timeout in seconds."""
        if self._timeout is not None:
            t = self._timeout
        elif self.console and self.console.startswith("ttyS"):
            t = 5
        else:
            t = 20

        return t

    # pylint: disable-msg=E0102,E0202,E1101
    @timeout.setter
    def timeout(self, seconds):
        self._timeout = seconds

    # pylint: disable-msg=E0202
    @property
    def update_only(self):
        return self._update_only

    # pylint: disable-msg=E0102,E0202,E1101
    @update_only.setter
    def update_only(self, value):
        if value and not self.can_update:
            raise ValueError("this bootloader does not support updates")
        elif self.can_update:
            self._update_only = value

    def set_boot_args(self, *args, **kwargs):
        """ Set up the boot command line.

            Keyword Arguments:

                network - a pyanaconda.network.Network instance (for network
                          storage devices' boot arguments)

            All other arguments are expected to have a dracutSetupArgs()
            method.
        """
        network = kwargs.pop("network", None)

        #
        # FIPS
        #
        if flags.cmdline.get("fips") == "1":
            self.boot_args.add("boot=%s" % self.stage2_device.fstabSpec)

        #
        # dracut
        #

        # storage
        from pyanaconda.storage.devices import NetworkStorageDevice
        dracut_devices = [self.storage.rootDevice]
        if self.stage2_device != self.storage.rootDevice:
            dracut_devices.append(self.stage2_device)

        dracut_devices.extend(self.storage.fsset.swapDevices)

        done = []
        # When we see a device whose setup string starts with a key in this
        # dict we pop that pair from the dict. When we're done looking at
        # devices we are left with the values that belong in the boot args.
        dracut_storage = {"rd.luks.uuid": "rd.luks=0",
                          "rd.lvm.lv": "rd.lvm=0",
                          "rd.md.uuid": "rd.md=0",
                          "rd.dm.uuid": "rd.dm=0"}
        for device in dracut_devices:
            for dep in self.storage.devices:
                if dep in done:
                    continue

                if device != dep and not device.dependsOn(dep):
                    continue

                setup_args = dep.dracutSetupArgs()
                if not setup_args:
                    continue

                self.boot_args.update(setup_args)
                self.dracut_args.update(setup_args)
                done.append(dep)
                for setup_arg in setup_args:
                    dracut_storage.pop(setup_arg.split("=")[0], None)

                # network storage
                # XXX this is nothing to be proud of
                if isinstance(dep, NetworkStorageDevice):
                    if network is None:
                        log.error("missing network instance for setup of boot "
                                  "command line for network storage device %s"
                                  % dep.name)
                        raise BootLoaderError("missing network instance when "
                                              "setting boot args for network "
                                              "storage device")

                    setup_args = network.dracutSetupArgs(dep)
                    self.boot_args.update(setup_args)
                    self.dracut_args.update(setup_args)

        self.boot_args.update(dracut_storage.values())
        self.dracut_args.update(dracut_storage.values())

        # passed-in objects
        for cfg_obj in list(args) + kwargs.values():
            if hasattr(cfg_obj, "dracutSetupArgs"):
                setup_args = cfg_obj.dracutSetupArgs()
                self.boot_args.update(setup_args)
                self.dracut_args.update(setup_args)
            else:
                setup_string = cfg_obj.dracutSetupString()
                self.boot_args.add(setup_string)
                self.dracut_args.add(setup_string)

        #
        # preservation of some of our boot args
        # FIXME: this is stupid.
        #
        for opt in self.global_preserve_args + self.preserve_args:
            if opt not in flags.cmdline:
                continue

            arg = flags.cmdline.get(opt)
            new_arg = opt
            if arg:
                new_arg += "=%s" % arg

            self.boot_args.add(new_arg)

    #
    # configuration
    #

    @property
    def boot_prefix(self):
        """ Prefix, if any, to paths in /boot. """
        if self.stage2_device == self.storage.rootDevice:
            prefix = "/boot"
        else:
            prefix = ""

        return prefix

    def _set_console(self):
        """ Set console options based on boot arguments. """
        if flags.serial:
            console = flags.cmdline.get("console", "ttyS0").split(",", 1)
            self.console = console[0]
            if len(console) > 1:
                self.console_options = console[1]
        elif flags.virtpconsole:
            self.console = re.sub("^/dev/", "", flags.virtpconsole)

    def write_config_console(self, config):
        """Write console-related configuration lines."""
        pass

    def write_config_password(self, config):
        """Write password-related configuration lines."""
        pass

    def write_config_header(self, config):
        """Write global configuration lines."""
        self.write_config_console(config)
        self.write_config_password(config)

    def write_config_images(self, config):
        """Write image configuration entries."""
        # XXX might this be identical for yaboot and silo?
        raise NotImplementedError()

    def write_config_post(self):
        try:
            os.chmod(ROOT_PATH + self.config_file, self.config_file_mode)
        except OSError as e:
            log.error("failed to set config file permissions: %s" % e)

    def write_config(self):
        """ Write the bootloader configuration. """
        if not self.config_file:
            raise BootLoaderError("no config file defined for this bootloader")

        config_path = os.path.normpath(ROOT_PATH + self.config_file)
        if os.access(config_path, os.R_OK):
            os.rename(config_path, config_path + ".anacbak")

        config = open(config_path, "w")
        self.write_config_header(config)
        self.write_config_images(config)
        config.close()
        self.write_config_post()

    def writeKS(self, f):
        """ Write bootloader section of kickstart configuration. """
        if self.stage1_device.isDisk:
            location = "mbr"
        elif self.stage1_device:
            location = "partition"
        else:
            location = "none\n"

        f.write("bootloader --location=%s" % location)

        if not self.stage1_device:
            return

        if self.drive_order:
            f.write(" --driveorder=%s" % ",".join(self.drive_order))

        append = self.boot_args - self.dracut_args
        if append:
            f.write(" --append=\"%s\"" % append)

        f.write("\n")

    def read(self):
        """ Read an existing bootloader configuration. """
        raise NotImplementedError()

    @property
    def trusted_boot(self):
        return self._trusted_boot

    @trusted_boot.setter
    def trusted_boot(self, trusted_boot):
        self._trusted_boot = trusted_boot

    #
    # installation
    #
    def write(self):
        """ Write the bootloader configuration and install the bootloader. """
        if self.update_only:
            self.update()
            return

        self.write_config()
        sync()
        self.stage2_device.format.sync(root=ROOT_PATH)
        self.install()

    def install(self):
        raise NotImplementedError()

    def update(self):
        """ Update an existing bootloader configuration. """
        pass


class GRUB(BootLoader):
    name = "GRUB"
    _config_dir = "grub"
    _config_file = "grub.conf"
    _device_map_file = "device.map"
    can_dual_boot = True
    can_update = True

    stage2_is_valid_stage1 = True
    stage2_bootable = True

    # list of strings representing options for boot device types
    stage2_device_types = ["partition", "mdarray"]
    stage2_raid_levels = [mdraid.RAID1]
    stage2_raid_member_types = ["partition"]
    stage2_raid_metadata = ["0", "0.90", "1.0"]

    packages = ["grub"]

    def __init__(self, storage):
        super(GRUB, self).__init__(storage)
        self.encrypted_password = ""

    #
    # grub-related conveniences
    #

    def grub_device_name(self, device):
        """ Return a grub-friendly representation of device. """
        drive = getattr(device, "disk", device)
        name = "(hd%d" % self.drives.index(drive)
        if hasattr(device, "disk"):
            name += ",%d" % (device.partedPartition.number - 1,)
        name += ")"
        return name

    @property
    def grub_config_dir(self):
        """ Config dir, adjusted for grub's view of the world. """
        return self.boot_prefix + self._config_dir

    #
    # configuration
    #

    @property
    def config_dir(self):
        """ Full path to configuration directory. """
        return "/boot/" + self._config_dir

    @property
    def config_file(self):
        """ Full path to configuration file. """
        return "%s/%s" % (self.config_dir, self._config_file)

    @property
    def device_map_file(self):
        """ Full path to device.map file. """
        return "%s/%s" % (self.config_dir, self._device_map_file)

    @property
    def grub_conf_device_line(self):
        return ""

    @property
    def serial_command(self):
        command = ""
        if self.console and self.console.startswith("ttyS"):
            unit = self.console[-1]
            speed = "9600"
            for opt in self.console_options.split(","):
                if opt.isdigit:
                    speed = opt
                    break

            command = "serial --unit=%s --speed=%s" % (unit, speed)

        return command

    def write_config_console(self, config):
        """ Write console-related configuration. """
        if not self.console:
            return

        if self.console.startswith("ttyS"):
            config.write("%s\n" % self.serial_command)
            config.write("terminal --timeout=%s serial console\n"
                         % self.timeout)

        console_arg = "console=%s" % self.console
        if self.console_options:
            console_arg += ",%s" % self.console_options
        self.boot_args.add(console_arg)

    def _encrypt_password(self):
        """ Make sure self.encrypted_password is set up correctly. """
        if self.encrypted_password:
            return

        if not self.password:
            raise BootLoaderError("cannot encrypt empty password")

        import string
        import crypt
        import random
        salt = "$6$"
        salt_len = 16
        salt_chars = string.letters + string.digits + './'

        rand_gen = random.SystemRandom()
        salt += "".join([rand_gen.choice(salt_chars) for i in range(salt_len)])
        self.encrypted_password = crypt.crypt(self.password, salt)

    def write_config_password(self, config):
        """ Write password-related configuration. """
        if not self.password and not self.encrypted_password:
            return

        self._encrypt_password()
        password_line = "--encrypted " + self.encrypted_password
        config.write("password %s\n" % password_line)

    def write_config_header(self, config):
        """Write global configuration information. """
        if self.boot_prefix:
            have_boot = "do not "
        else:
            have_boot = ""

        s = """# grub.conf generated by anaconda
# Note that you do not have to rerun grub after making changes to this file.
# NOTICE:  You %(do)shave a /boot partition. This means that all kernel and
#          initrd paths are relative to %(boot)s, eg.
#          root %(grub_target)s
#          kernel %(prefix)s/vmlinuz-version ro root=%(root_device)s
#          initrd %(prefix)s/initrd-[generic-]version.img
""" % {"do": have_boot, "boot": self.stage2_device.format.mountpoint,
       "root_device": self.stage2_device.path,
       "grub_target": self.grub_device_name(self.stage1_device),
       "prefix": self.boot_prefix}

        config.write(s)
        config.write("boot=%s\n" % self.stage1_device.path)
        config.write(self.grub_conf_device_line)

        # find the index of the default image
        try:
            default_index = self.images.index(self.default)
        except ValueError:
            e = "Failed to find default image (%s)" % self.default.label
            raise BootLoaderError(e)

        config.write("default=%d\n" % default_index)
        config.write("timeout=%d\n" % self.timeout)

        self.write_config_console(config)

        if not flags.serial:
            splash = "splash.xpm.gz"
            splash_path = os.path.normpath("%s%s/%s" % (ROOT_PATH,
                                                        self.config_dir,
                                                        splash))
            if os.access(splash_path, os.R_OK):
                grub_root_grub_name = self.grub_device_name(self.stage2_device)
                config.write("splashimage=%s/%s/%s\n" % (grub_root_grub_name,
                                                         self.grub_config_dir,
                                                         splash))
                config.write("hiddenmenu\n")

        self.write_config_password(config)

    def write_config_images(self, config):
        """ Write image entries into configuration file. """
        for image in self.images:
            if isinstance(image, LinuxBootLoaderImage):
                args = Arguments()
                grub_root = self.grub_device_name(self.stage2_device)
                args.update(["ro", "root=%s" % image.device.fstabSpec])
                args.update(self.boot_args)
                if isinstance(image, TbootLinuxBootLoaderImage):
                    args.update(image.args)
                    snippet = ("\tkernel %(prefix)s/%(multiboot)s %(mbargs)s\n"
                               "\tmodule %(prefix)s/%(kernel)s %(args)s\n"
                               "\tmodule %(prefix)s/%(initrd)s\n"
                               % {"prefix": self.boot_prefix,
                                  "multiboot": image.multiboot,
                                  "mbargs": image.mbargs,
                                  "kernel": image.kernel, "args": args,
                                  "initrd": image.initrd})
                else:
                    snippet = ("\tkernel %(prefix)s/%(kernel)s %(args)s\n"
                               "\tinitrd %(prefix)s/%(initrd)s\n"
                               % {"prefix": self.boot_prefix,
                                  "kernel": image.kernel, "args": args,
                                  "initrd": image.initrd})
                stanza = ("title %(label)s (%(version)s)\n"
                          "\troot %(grub_root)s\n"
                          "%(snippet)s"
                          % {"label": image.label, "version": image.version,
                             "grub_root": grub_root, "snippet": snippet})
            else:
                stanza = ("title %(label)s\n"
                          "\trootnoverify %(grub_root)s\n"
                          "\tchainloader +1\n"
                          % {"label": image.label,
                             "grub_root": self.grub_device_name(image.device)})

            config.write(stanza)

    def write_device_map(self):
        """ Write out a device map containing all supported devices. """
        map_path = os.path.normpath(ROOT_PATH + self.device_map_file)
        if os.access(map_path, os.R_OK):
            os.rename(map_path, map_path + ".anacbak")

        dev_map = open(map_path, "w")
        dev_map.write("# this device map was generated by anaconda\n")
        for drive in self.drives:
            dev_map.write("%s      %s\n" % (self.grub_device_name(drive),
                                            drive.path))
        dev_map.close()

    def write_config_post(self):
        """ Perform additional configuration after writing config file(s). """
        super(GRUB, self).write_config_post()

        # make symlink for menu.lst (grub's default config file name)
        menu_lst = "%s%s/menu.lst" % (ROOT_PATH, self.config_dir)
        if os.access(menu_lst, os.R_OK):
            try:
                os.rename(menu_lst, menu_lst + '.anacbak')
            except OSError as e:
                log.error("failed to back up %s: %s" % (menu_lst, e))

        try:
            os.symlink(self._config_file, menu_lst)
        except OSError as e:
            log.error("failed to create grub menu.lst symlink: %s" % e)

        # make symlink to grub.conf in /etc since that's where configs belong
        etc_grub = "%s/etc/%s" % (ROOT_PATH, self._config_file)
        if os.access(etc_grub, os.R_OK):
            try:
                os.unlink(etc_grub)
            except OSError as e:
                log.error("failed to remove %s: %s" % (etc_grub, e))

        try:
            os.symlink("..%s" % self.config_file, etc_grub)
        except OSError as e:
            log.error("failed to create /etc/grub.conf symlink: %s" % e)

    def write_config(self):
        """ Write bootloader configuration to disk. """
        # write device.map
        self.write_device_map()

        # this writes the actual configuration file
        super(GRUB, self).write_config()

    #
    # installation
    #

    @property
    def install_targets(self):
        """ List of (stage1, stage2) tuples representing install targets. """
        targets = []
        if self.stage2_device.type == "mdarray" and \
           self.stage2_device.level == 1:
            # make sure we have stage1 and stage2 installed with redundancy
            # so that boot can succeed even in the event of failure or removal
            # of some of the disks containing the member partitions of the
            # /boot array
            for stage2dev in self.stage2_device.parents:
                if self.stage1_device.isDisk:
                    # install to mbr
                    if self.stage2_device.dependsOn(self.stage1_device):
                        # if target disk contains any of /boot array's member
                        # partitions, set up stage1 on each member's disk
                        # and stage2 on each member partition
                        stage1dev = stage2dev.disk
                    else:
                        # if target disk does not contain any of /boot array's
                        # member partitions, install stage1 to the target disk
                        # and stage2 to each of the member partitions
                        stage1dev = self.stage1_device
                else:
                    # target is /boot device and /boot is raid, so install
                    # grub to each of /boot member partitions
                    stage1dev = stage2dev

                targets.append((stage1dev, stage2dev))
        else:
            targets.append((self.stage1_device, self.stage2_device))

        return targets

    def install(self):
        rc = iutil.execWithRedirect("grub-install", ["--just-copy"],
                                    stdout="/dev/tty5", stderr="/dev/tty5",
                                    root=ROOT_PATH)
        if rc:
            raise BootLoaderError("bootloader install failed")

        for (stage1dev, stage2dev) in self.install_targets:
            cmd = ("root %(stage2dev)s\n"
                   "install --stage2=%(config_dir)s/stage2"
                   " /%(grub_config_dir)s/stage1 d %(stage1dev)s"
                   " /%(grub_config_dir)s/stage2 p"
                   " %(stage2dev)s/%(grub_config_dir)s/%(config_basename)s\n"
                   % {"grub_config_dir": self.grub_config_dir,
                      "config_dir": self.config_dir,
                      "config_basename": self._config_file,
                      "stage1dev": self.grub_device_name(self.stage1_device),
                      "stage2dev": self.grub_device_name(self.stage2_device)})
            (pread, pwrite) = os.pipe()
            os.write(pwrite, cmd)
            os.close(pwrite)
            args = ["--batch", "--no-floppy",
                    "--device-map=%s" % self.device_map_file]
            rc = iutil.execWithRedirect("grub", args,
                                        stdout="/dev/tty5", stderr="/dev/tty5",
                                        stdin=pread, root=ROOT_PATH)
            os.close(pread)
            if rc:
                raise BootLoaderError("bootloader install failed")

    def update(self):
        self.install()

    #
    # miscellaneous
    #

    @property
    def has_windows(self):
        return len(self.bootable_chain_devices) != 0


class EFIGRUB(GRUB):
    can_dual_boot = False
    _config_dir = "efi/EFI/redhat"

    stage2_is_valid_stage1 = False
    stage2_bootable = False
    stage2_max_end_mb = None

    def efibootmgr(self, *args, **kwargs):
        if kwargs.pop("capture", False):
            exec_func = iutil.execWithCapture
        else:
            exec_func = iutil.execWithRedirect

        return exec_func("efibootmgr", list(args), **kwargs)

    #
    # configuration
    #

    @property
    def efi_product_path(self):
        """ The EFI product path.

            eg: HD(1,800,64000,faacb4ef-e361-455e-bd97-ca33632550c3)
        """
        buf = self.efibootmgr("-v", stderr="/dev/tty5", capture=True)
        matches = re.search(productName + r'\s+(HD\(.+?\))', buf)
        if matches and matches.groups():
            return matches.group(1)
        return ""

    @property
    def grub_conf_device_line(self):
        return "device %s %s\n" % (self.grub_device_name(self.stage2_device),
                                   self.efi_product_path)

    #
    # installation
    #

    def remove_efi_boot_target(self):
        buf = self.efibootmgr(capture=True)
        for line in buf.splitlines():
            try:
                (slot, _product) = line.split(None, 1)
            except ValueError:
                continue

            if _product == productName:
                slot_id = slot[4:8]
                if not slot_id.isdigit():
                    log.warning("failed to parse efi boot slot (%s)" % slot)
                    continue

                rc = self.efibootmgr("-b", slot_id, "-B",
                                     root=ROOT_PATH,
                                     stdout="/dev/tty5", stderr="/dev/tty5")
                if rc:
                    raise BootLoaderError("failed to remove old efi boot entry")

    def add_efi_boot_target(self):
        boot_efi = self.storage.mountpoints["/boot/efi"]
        if boot_efi.type == "partition":
            boot_disk = boot_efi.disk
            boot_part_num = boot_efi.partedPartition.number
        elif boot_efi.type == "mdarray":
            # FIXME: I'm just guessing here. This probably needs the full
            #        treatment, ie: multiple targets for each member.
            boot_disk = boot_efi.parents[0].disk
            boot_part_num = boot_efi.parents[0].partedPartition.number
        boot_part_num = str(boot_part_num)

        rc = self.efibootmgr("-c", "-w", "-L", productName,
                             "-d", boot_disk.path, "-p", boot_part_num,
                             "-l", "\\EFI\\redhat\\grub.efi",
                             root=ROOT_PATH,
                             stdout="/dev/tty5", stderr="/dev/tty5")
        if rc:
            raise BootLoaderError("failed to set new efi boot target")

    def install(self):
        self.remove_efi_boot_target()
        self.add_efi_boot_target()

    def update(self):
        self.write()

class GRUB2(GRUB):
    """ GRUBv2

        - configuration
            - password (insecure), password_pbkdf2
                - http://www.gnu.org/software/grub/manual/grub.html#Invoking-grub_002dmkpasswd_002dpbkdf2
            - --users per-entry specifies which users can access, otherwise
              entry is unrestricted
            - /etc/grub/custom.cfg

        - how does grub resolve names of md arrays?

        - disable automatic use of grub-mkconfig?
            - on upgrades?

        - BIOS boot partition (GPT)
            - parted /dev/sda set <partition_number> bios_grub on
            - can't contain a filesystem
            - 31KiB min, 1MiB recommended

    """
    name = "GRUB2"
    packages = ["grub2", "gettext", "os-prober"]
    _config_file = "grub.cfg"
    _config_dir = "grub2"
    config_file_mode = 0600
    defaults_file = "/etc/default/grub"
    can_dual_boot = True
    can_update = True

    # requirements for boot devices
    stage2_format_types = ["ext4", "ext3", "ext2", "btrfs"]
    stage2_device_types = ["partition", "mdarray", "lvmlv"]
    stage2_raid_levels = [mdraid.RAID0, mdraid.RAID1, mdraid.RAID4,
                          mdraid.RAID5, mdraid.RAID6, mdraid.RAID10]

    # XXX we probably need special handling for raid stage1 w/ gpt disklabel
    #     since it's unlikely there'll be a bios boot partition on each disk

    #
    # constraints for target devices
    #
    def _gpt_disk_has_bios_boot(self, device):
        """ Return False if device is gpt-labeled disk w/o bios boot part. """
        ret = True

        if device is None:
            return ret

        if self.stage1_device == self.stage2_device:
            # if we're booting from the stage2 device there's probably no
            # need for a BIOS boot partition
            return ret

        # check that a bios boot partition is present if the stage1 device
        # is a gpt-labeled disk
        if device.isDisk and getattr(device.format, "labelType", None) == "gpt":
            ret = False
            partitions = [p for p in self.storage.partitions
                          if p.disk == device]
            for p in partitions:
                if p.format.type == "biosboot":
                    ret = True
                    break

            if not ret:
                self.warnings.append(_("You are using a GPT bootdisk on a BIOS "
                                   "system without a BIOS boot partition. This "
                                   "may not work, depending on your BIOS's "
                                   "support for booting from GPT disks."))

        log.debug("_gpt_disk_has_bios_boot(%s) returning %s" % (device.name,
                                                                ret))
        return ret

    def is_valid_stage1_device(self, device):
        ret = super(GRUB2, self).is_valid_stage1_device(device)
        if ret:
            ignored = self._gpt_disk_has_bios_boot(device)

        log.debug("is_valid_stage1_device(%s) returning %s" % (device.name,
                                                                ret))
        return ret

    #
    # grub-related conveniences
    #

    def grub_device_name(self, device):
        """ Return a grub-friendly representation of device.

            Disks and partitions use the (hdX,Y) notation, while lvm and
            md devices just use their names.
        """
        drive = None
        name = "(%s)" % device.name

        if device.isDisk:
            drive = device
        elif hasattr(device, "disk"):
            drive = device.disk

        if drive is not None:
            name = "(hd%d" % self.drives.index(drive)
            if hasattr(device, "disk"):
                name += ",%d" % device.partedPartition.number
            name += ")"
        return name

    def write_config_console(self, config):
        if not self.console:
            return

        console_arg = "console=%s" % self.console
        if self.console_options:
            console_arg += ",%s" % self.console_options
        self.boot_args.add(console_arg)

    def write_device_map(self):
        """ Write out a device map containing all supported devices. """
        map_path = os.path.normpath(ROOT_PATH + self.device_map_file)
        if os.access(map_path, os.R_OK):
            os.rename(map_path, map_path + ".anacbak")

        dev_map = open(map_path, "w")
        dev_map.write("# this device map was generated by anaconda\n")
        devices = self.drives
        if self.stage1_device not in devices:
            devices.append(self.stage1_device)

        if self.stage2_device not in devices:
            devices.append(self.stage2_device)

        for drive in devices:
            dev_map.write("%s      %s\n" % (self.grub_device_name(drive),
                                            drive.path))
        dev_map.close()

    def write_defaults(self):
        defaults_file = "%s%s" % (ROOT_PATH, self.defaults_file)
        defaults = open(defaults_file, "w+")
        defaults.write("GRUB_TIMEOUT=%d\n" % self.timeout)
        defaults.write("GRUB_DISTRIBUTOR=\"%s\"\n" % productName)
        defaults.write("GRUB_DEFAULT=saved\n")
        if self.console and self.console.startswith("ttyS"):
            defaults.write("GRUB_TERMINAL=\"serial console\"\n")
            defaults.write("GRUB_SERIAL_COMMAND=\"%s\"\n" % self.serial_command)

        # this is going to cause problems for systems containing multiple
        # linux installations or even multiple boot entries with different
        # boot arguments
        defaults.write("GRUB_CMDLINE_LINUX=\"%s\"\n" % self.boot_args)
        defaults.close()

    def _encrypt_password(self):
        """ Make sure self.encrypted_password is set up properly. """
        if self.encrypted_password:
            return

        if not self.password:
            raise RuntimeError("cannot encrypt empty password")

        (pread, pwrite) = os.pipe()
        os.write(pwrite, "%s\n%s\n" % (self.password, self.password))
        os.close(pwrite)
        buf = iutil.execWithCapture("grub2-mkpasswd-pbkdf2", [],
                                    stdin=pread,
                                    stderr="/dev/tty5",
                                    root=ROOT_PATH)
        os.close(pread)
        self.encrypted_password = buf.split()[-1].strip()
        if not self.encrypted_password.startswith("grub.pbkdf2."):
            raise BootLoaderError("failed to encrypt bootloader password")

    def write_password_config(self):
        if not self.password and not self.encrypted_password:
            return

        users_file = ROOT_PATH + "/etc/grub.d/01_users"
        header = open(users_file, "w")
        header.write("#!/bin/sh -e\n\n")
        header.write("cat << EOF\n")
        # XXX FIXME: document somewhere that the username is "root"
        header.write("set superusers=\"root\"\n")
        self._encrypt_password()
        password_line = "password_pbkdf2 root " + self.encrypted_password
        header.write("%s\n" % password_line)
        header.write("EOF\n")
        header.close()
        os.chmod(users_file, 0755)

    def write_config(self):
        self.write_config_console(None)
        self.write_device_map()
        self.write_defaults()

        # if we fail to setup password auth we should complete the
        # installation so the system is at least bootable
        try:
            self.write_password_config()
        except (BootLoaderError, OSError, RuntimeError) as e:
            log.error("bootloader password setup failed: %s" % e)

        # make sure the default entry is the OS we are installing
        entry_title = "%s Linux, with Linux %s" % (productName,
                                                   self.default.version)
        rc = iutil.execWithRedirect("grub2-set-default",
                                    [entry_title],
                                    root=ROOT_PATH,
                                    stdout="/dev/tty5", stderr="/dev/tty5")
        if rc:
            log.error("failed to set default menu entry to %s" % productName)

        # now tell grub2 to generate the main configuration file
        rc = iutil.execWithRedirect("grub2-mkconfig",
                                    ["-o", self.config_file],
                                    root=ROOT_PATH,
                                    stdout="/dev/tty5", stderr="/dev/tty5")
        if rc:
            raise BootLoaderError("failed to write bootloader configuration")

    #
    # installation
    #

    def install(self):
        # XXX will installing to multiple drives work as expected with GRUBv2?
        for (stage1dev, stage2dev) in self.install_targets:
            args = ["--no-floppy", self.grub_device_name(stage1dev)]
            if stage1dev == stage2dev:
                # This is hopefully a temporary hack. GRUB2 currently refuses
                # to install to a partition's boot block without --force.
                args.insert(0, '--force')

            rc = iutil.execWithRedirect("grub2-install", args,
                                        stdout="/dev/tty5", stderr="/dev/tty5",
                                        root=ROOT_PATH)
            if rc:
                raise BootLoaderError("bootloader install failed")


class YabootSILOBase(BootLoader):
    def write_config_password(self, config):
        if self.password:
            config.write("password=%s\n" % self.password)
            config.write("restricted\n")

    def write_config_images(self, config):
        for image in self.images:
            if not isinstance(image, LinuxBootLoaderImage):
                # mac os images are handled specially in the header on mac
                continue

            args = Arguments()
            if image.initrd:
                initrd_line = "\tinitrd=%s/%s\n" % (self.boot_prefix,
                                                    image.initrd)
            else:
                initrd_line = ""

            root_device_spec = self.storage.rootDevice.fstabSpec
            if root_device_spec.startswith("/"):
                root_line = "\troot=%s\n" % root_device_spec
            else:
                args.add("root=%s" % root_device_spec)
                root_line = ""

            args.update(self.boot_args)

            stanza = ("image=%(boot_prefix)s%(kernel)s\n"
                      "\tlabel=%(label)s\n"
                      "\tread-only\n"
                      "%(initrd_line)s"
                      "%(root_line)s"
                      "\tappend=\"%(args)s\"\n\n"
                      % {"kernel": image.kernel,  "initrd_line": initrd_line,
                         "label": self.image_label(image),
                         "root_line": root_line, "args": args,
                         "boot_prefix": self.boot_prefix})
            config.write(stanza)


class Yaboot(YabootSILOBase):
    name = "Yaboot"
    _config_file = "yaboot.conf"
    prog = "ybin"
    image_label_attr = "short_label"
    packages = ["yaboot"]

    # stage2 device requirements
    stage2_device_types = ["partition", "mdarray"]
    stage2_device_raid_levels = [mdraid.RAID1]

    def __init__(self, storage):
        BootLoader.__init__(self, storage)

    #
    # configuration
    #

    @property
    def config_dir(self):
        conf_dir = "/etc"
        if self.stage2_device.format.mountpoint == "/boot":
            conf_dir = "/boot/etc"
        return conf_dir

    @property
    def config_file(self):
        return "%s/%s" % (self.config_dir, self._config_file)

    def write_config_header(self, config):
        if self.stage2_device.type == "mdarray":
            boot_part_num = self.stage2_device.parents[0].partedPartition.number
        else:
            boot_part_num = self.stage2_device.partedPartition.number

        # yaboot.conf timeout is in tenths of a second. Brilliant.
        header = ("# yaboot.conf generated by anaconda\n\n"
                  "boot=%(stage1dev)s\n"
                  "init-message=\"Welcome to %(product)s!\\nHit <TAB> for "
                  "boot options\"\n\n"
                  "partition=%(part_num)d\n"
                  "timeout=%(timeout)d\n"
                  "install=/usr/lib/yaboot/yaboot\n"
                  "delay=5\n"
                  "enablecdboot\n"
                  "enableofboot\n"
                  "enablenetboot\n"
                  % {"stage1dev": self.stage1_device.path,
                     "product": productName, "part_num": boot_part_num,
                     "timeout": self.timeout * 10})
        config.write(header)
        self.write_config_variant_header(config)
        self.write_config_password(config)
        config.write("\n")

    def write_config_variant_header(self, config):
        config.write("nonvram\n")
        config.write("mntpoint=/boot/yaboot\n")
        config.write("usemount\n")

    def write_config_post(self):
        super(Yaboot, self).write_config_post()

        # make symlink in /etc to yaboot.conf if config is in /boot/etc
        etc_yaboot_conf = ROOT_PATH + "/etc/yaboot.conf"
        if not os.access(etc_yaboot_conf, os.R_OK):
            try:
                os.symlink("../boot/etc/yaboot.conf", etc_yaboot_conf)
            except OSError as e:
                log.error("failed to create /etc/yaboot.conf symlink: %s" % e)

    def write_config(self):
        if not os.path.isdir(ROOT_PATH + self.config_dir):
            os.mkdir(ROOT_PATH + self.config_dir)

        # this writes the config
        super(Yaboot, self).write_config()

    #
    # installation
    #

    def install(self):
        args = ["-f", "-C", self.config_file]
        rc = iutil.execWithRedirect(self.prog, args,
                                    stdout="/dev/tty5", stderr="/dev/tty5",
                                    root=ROOT_PATH)
        if rc:
            raise BootLoaderError("bootloader installation failed")


class IPSeriesYaboot(Yaboot):
    prog = "mkofboot"

    #
    # configuration
    #

    def write_config_variant_header(self, config):
        config.write("nonvram\n")   # only on pSeries?
        config.write("fstype=raw\n")


class MacYaboot(Yaboot):
    prog = "mkofboot"
    can_dual_boot = True

    #
    # configuration
    #

    def write_config_variant_header(self, config):
        try:
            mac_os = [i for i in self.chain_images if i.label][0]
        except IndexError:
            pass
        else:
            config.write("macosx=%s\n" % mac_os.device.path)

        config.write("magicboot=/usr/lib/yaboot/ofboot\n")


class ZIPL(BootLoader):
    name = "ZIPL"
    config_file = "/etc/zipl.conf"
    packages = ["s390utils-base"]

    # stage2 device requirements
    stage2_device_types = ["partition", "mdarray", "lvmlv"]
    stage2_device_raid_levels = [mdraid.RAID1]

    image_label_attr = "short_label"
    preserve_args = ["cio_ignore"]

    #
    # configuration
    #

    @property
    def boot_dir(self):
        return "/boot"

    def write_config_images(self, config):
        for image in self.images:
            args = Arguments()
            if image.initrd:
                initrd_line = "\tramdisk=%s/%s\n" % (self.boot_dir,
                                                     image.initrd)
            else:
                initrd_line = ""
            args.add("root=%s/%s" % (self.boot_dir, image.kernel))
            args.update(self.boot_args)
            stanza = ("[%(label)s]\n"
                      "\timage=%(boot_dir)s/%(kernel)s\n"
                      "%(initrd_line)s"
                      "\tparameters=\"%(args)s\"\n"
                      % {"label": self.image_label(image),
                         "kernel": image.kernel, "initrd_line": initrd_line,
                         "args": args,
                         "boot_dir": self.boot_dir})
            config.write(stanza)

    def write_config_header(self, config):
        header = ("[defaultboot]\n"
                  "timeout=%(timeout)d\n"
                  "default=%(default)s\n"
                  "target=/boot\n"
                  % {"timeout": self.timeout,
                     "default": self.image_label(self.default)})
        config.write(header)

    #
    # installation
    #

    def install(self):
        buf = iutil.execWithCapture("zipl", [],
                                    stderr="/dev/tty5",
                                    root=ROOT_PATH)
        for line in buf.splitlines():
            if line.startswith("Preparing boot device: "):
                # Output here may look like:
                #     Preparing boot device: dasdb (0200).
                #     Preparing boot device: dasdl.
                # We want to extract the device name and pass that.
                name = re.sub(".+?: ", "", line)
                name = re.sub("(\s\(.+\))?\.$", "", name)
                device = self.storage.devicetree.getDeviceByName(name)
                if not device:
                    raise BootLoaderError("could not find IPL device")

                self.stage1_device = device


class SILO(YabootSILOBase):
    name = "SILO"
    _config_file = "silo.conf"
    message_file = "/etc/silo.message"

    # stage1 device requirements
    stage1_device_types = ["disk"]

    # stage2 device requirements
    stage2_device_types = ["partition"]

    packages = ["silo"]

    image_label_attr = "short_label"

    #
    # configuration
    #

    @property
    def config_dir(self):
        if self.stage2_device.format.mountpoint == "/boot":
            return "/boot"
        else:
            return "/etc"

    @property
    def config_file(self):
        return "%s/%s" % (self.config_dir, self._config_file)

    def write_message_file(self):
        message_file = os.path.normpath(ROOT_PATH + self.message_file)
        f = open(message_file, "w")
        f.write("Welcome to %s!\nHit <TAB> for boot options\n\n" % productName)
        f.close()
        os.chmod(message_file, 0600)

    def write_config_header(self, config):
        header = ("# silo.conf generated by anaconda\n\n"
                  "#boot=%(stage1dev)s\n"
                  "message=%(message)s\n"
                  "timeout=%(timeout)d\n"
                  "partition=%(boot_part_num)d\n"
                  "default=%(default)s\n"
                  % {"stage1dev": self.stage1_device.path,
                     "message": self.message_file, "timeout": self.timeout,
                     "boot_part_num": self.stage1_device.partedPartition.number,
                     "default": self.image_label(self.default)})
        config.write(header)
        self.write_config_password(config)

    def write_config_post(self):
        etc_silo = os.path.normpath(ROOT_PATH + "/etc/" + self._config_file)
        if not os.access(etc_silo, os.R_OK):
            try:
                os.symlink("../boot/%s" % self._config_file, etc_silo)
            except OSError as e:
                log.warning("failed to create /etc/silo.conf symlink: %s" % e)

    def write_config(self):
        self.write_message_file()
        super(SILO, self).write_config()

    #
    # installation
    #

    def install(self):
        backup = "%s/backup.b" % self.config_dir
        args = ["-f", "-C", self.config_file, "-S", backup]
        variant = iutil.getSparcMachine()
        if variant in ("sun4u", "sun4v"):
            args.append("-u")
        else:
            args.append("-U")

        rc = iutil.execWithRedirect("silo", args,
                                    stdout="/dev/tty5", stderr="/dev/tty5",
                                    root=ROOT_PATH)

        if rc:
            raise BootLoaderError("bootloader install failed")


# anaconda-specific functions

def writeSysconfigKernel(anaconda, default_kernel):
    f = open(ROOT_PATH + "/etc/sysconfig/kernel", "w+")
    f.write("# UPDATEDEFAULT specifies if new-kernel-pkg should make\n"
            "# new kernels the default\n")
    # only update the default if we're setting the default to linux (#156678)
    if anaconda.bootloader.default.device == anaconda.storage.rootDevice:
        f.write("UPDATEDEFAULT=yes\n")
    else:
        f.write("UPDATEDEFAULT=no\n")
    f.write("\n")
    f.write("# DEFAULTKERNEL specifies the default kernel package type\n")
    f.write("DEFAULTKERNEL=%s\n" % default_kernel)
    f.close()


def writeBootloader(anaconda):
    """ Write bootloader configuration to disk.

        When we get here, the bootloader will already have a default linux
        image. We only have to add images for the non-default kernels and
        adjust the default to reflect whatever the default variant is.
    """

    # TODO: Verify the bootloader configuration has all it needs.
    #
    #       - zipl doesn't need to have a stage1 device set.
    #       - Isn't it possible for stage1 to be unset on iSeries if not using
    #         yaboot? If so, presumably they told us not to install any
    #         bootloader.
    stage1_device = anaconda.bootloader.stage1_device
    log.info("bootloader stage1 target device is %s" % stage1_device.name)
    stage2_device = anaconda.bootloader.stage2_device
    log.info("bootloader stage2 target device is %s" % stage2_device.name)

    w = None
    if anaconda.intf:
        w = anaconda.intf.waitWindow(_("Bootloader"),
                                     _("Installing bootloader."))

    # get a list of installed kernel packages
    kernel_versions = anaconda.backend.kernelVersionList()
    if not kernel_versions:
        log.warning("no kernel was installed -- bootloader config unchanged")
        if anaconda.intf:
            anaconda.intf.messageWindow(_("Warning"),
                        _("No kernel packages were installed on the system. "
                          "Bootloader configuration will not be changed."))
        return

    # The first one is the default kernel. Update the bootloader's default
    # entry to reflect the details of the default kernel.
    (version, arch, nick) = kernel_versions.pop(0)
    default_image = anaconda.bootloader.default
    if not default_image:
        log.error("unable to find default image, bailing")
        if w:
            w.pop()
        return

    default_image.version = version

    # all the linux images' labels are based on the default image's
    base_label = default_image.label
    base_short = default_image.short_label

    # get the name of the default kernel package for use in
    # /etc/sysconfig/kernel
    default_kernel = "kernel"
    if nick != "base":
        default_kernel += "-%s" % nick

    # now add an image for each of the other kernels
    used = ["base"]
    for (version, arch, nick) in kernel_versions:
        if nick in used:
            nick += "-%s" % version

        used.append(nick)
        label = "%s-%s" % (base_label, nick)
        short = "%s-%s" % (base_short, nick)
        if anaconda.bootloader.trusted_boot:
            image = TbootLinuxBootLoaderImage(
                                         device=anaconda.storage.rootDevice,
                                         version=version,
                                         label=label, short=short)
        else:
            image = LinuxBootLoaderImage(device=anaconda.storage.rootDevice,
                                         version=version,
                                         label=label, short=short)
        anaconda.bootloader.add_image(image)

    # write out /etc/sysconfig/kernel
    writeSysconfigKernel(anaconda, default_kernel)

    # set up dracut/fips boot args
    anaconda.bootloader.set_boot_args(keyboard=anaconda.keyboard,
                                      language=anaconda.instLanguage,
                                      network=anaconda.network)

    try:
        anaconda.bootloader.write()
    except BootLoaderError as e:
        if anaconda.intf:
            anaconda.intf.messageWindow(_("Warning"),
                            _("There was an error installing the bootloader.  "
                              "The system may not be bootable."))
    finally:
        if w:
            w.pop()

