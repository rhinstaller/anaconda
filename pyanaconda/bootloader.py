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
#                    Matthew Miller <mattdm@redhat.com> (extlinux portion)
#

import collections
import os
import re
import struct
from parted import PARTITION_BIOS_GRUB

from pyanaconda import iutil
from blivet.devicelibs import mdraid
from pyanaconda.isys import sync
from pyanaconda.product import productName
from pyanaconda.flags import flags
from pyanaconda.constants import ROOT_PATH
from blivet.errors import StorageError
from blivet.fcoe import fcoe
import pyanaconda.network
from pyanaconda.nm import nm_device_hwaddress
from blivet import platform
from pyanaconda.i18n import _, N_

import logging
log = logging.getLogger("anaconda")

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

class serial_opts(object):
    def __init__(self):
        self.speed = None
        self.parity = None
        self.word = None
        self.stop = None
        self.flow = None

def parse_serial_opt(arg):
    """Parse and split serial console options.

    Documentation/kernel-parameters.txt says:
      ttyS<n>[,options]
                Use the specified serial port.  The options are of
                the form "bbbbpnf", where "bbbb" is the baud rate,
                "p" is parity ("n", "o", or "e"), "n" is number of
                bits, and "f" is flow control ("r" for RTS or
                omit it).  Default is "9600n8".
    but note that everything after the baud rate is optional, so these are
    all valid: 9600, 19200n, 38400n8, 9600e7r.
    Also note that the kernel assumes 1 stop bit; this can't be changed.
    """
    opts = serial_opts()
    m = re.match(r'\d+', arg)
    if m is None:
        return opts
    opts.speed = m.group()
    idx = len(opts.speed)
    try:
        opts.parity = arg[idx+0]
        opts.word   = arg[idx+1]
        opts.flow   = arg[idx+2]
    except IndexError:
        pass
    return opts

class BootLoaderError(Exception):
    pass

class Arguments(set):
    ordering_dict = {
        "rhgb" : 99,
        "quiet" : 100
        }

    def _merge_ip(self):
        """
        Find ip= arguments targetting the same interface and merge them.
        """
        # partition the input
        def partition_p(arg):
            # we are only interested in ip= parameters that use some kind of
            # automatic network setup:
            return arg.startswith("ip=") and arg.count(":") == 1
        ip_params = filter(partition_p, self)
        rest = set(filter(lambda p: not partition_p(p), self))

        # split at the colon:
        ip_params = map(lambda p: p.split(":"), ip_params)
        # create mapping from nics to their configurations
        config = collections.defaultdict(list)
        for (nic, cfg) in ip_params:
            config[nic].append(cfg)

        # generate the new parameters:
        ip_params = set()
        for nic in config:
            ip_params.add("%s:%s" % (nic, ",".join(sorted(config[nic]))))

        # update the set
        self.clear()
        self.update(rest)
        self.update(ip_params)
        return self

    def __str__(self):
        self._merge_ip()
        # sort the elements according to their values in ordering_dict. The
        # higher the number the closer to the final string the argument
        # gets. The default is 50.
        lst = sorted(self, key=lambda s: self.ordering_dict.get(s, 50))

        return " ".join(lst)

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
    stage2_device = None
    stage2_device_types = []
    stage2_raid_levels = []
    stage2_raid_metadata = []
    stage2_raid_member_types = []
    stage2_mountpoints = ["/boot", "/"]
    stage2_bootable = False
    stage2_must_be_primary = True
    stage2_description = N_("/boot filesystem")
    stage2_max_end_mb = 2 * 1024 * 1024

    @property
    def stage2_format_types(self):
        return ["ext4", "ext3", "ext2"]

    # this is so stupid...
    global_preserve_args = ["speakup_synth", "apic", "noapic", "apm", "ide",
                            "noht", "acpi", "video", "pci", "nodmraid",
                            "nompath", "nomodeset", "noiswmd", "fips",
                            "selinux"]
    preserve_args = []

    _trusted_boot = False

    def __init__(self):
        self.boot_args = Arguments()
        self.dracut_args = Arguments()

        self.disks = []
        self._disk_order = []

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

        self._update_only = False
        self.skip_bootloader = False

        self.errors = []
        self.warnings = []

        self.reset()

    def reset(self):
        """ Reset stage1 and stage2 values """
        # the device the bootloader will be installed on
        self.stage1_device = None

        # the "boot disk", meaning the disk stage1 _will_ go on
        self.stage1_disk = None

        self.stage2_device = None
        self.stage2_is_preferred_stage1 = False

        self.errors = []
        self.problems = []
        self.warnings = []

    #
    # disk list access
    #
    # pylint: disable-msg=E0202
    @property
    def disk_order(self):
        """Potentially partial order for disks."""
        return self._disk_order

    # pylint: disable-msg=E0102,E0202,E1101
    @disk_order.setter
    def disk_order(self, order):
        log.debug("new disk order: %s", order)
        self._disk_order = order
        if self.disks:
            self._sort_disks()

    def _sort_disks(self):
        """Sort the internal disk list. """
        for name in reversed(self.disk_order):
            try:
                idx = [d.name for d in self.disks].index(name)
            except ValueError:
                log.error("bios order specified unknown disk %s", name)
                continue

            self.disks.insert(0, self.disks.pop(idx))

    def set_disk_list(self, disks):
        self.disks = disks[:]
        self._sort_disks()

    #
    # image list access
    #
    # pylint: disable-msg=E0202
    @property
    def default(self):
        """The default image."""
        if not self._default_image and self.linux_images:
            self._default_image = self.linux_images[0]

        return self._default_image

    # pylint: disable-msg=E0102,E0202,E1101
    @default.setter
    def default(self, image):
        if image not in self.images:
            raise ValueError("new default image not in image list")

        log.debug("new default image: %s", image)
        self._default_image = image

    @property
    def images(self):
        """ List of OS images that will be included in the configuration. """
        all_images = self.linux_images
        all_images.extend(i for i in self.chain_images if i.label)
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

    #
    # platform-specific data access
    #
    @property
    def disklabel_types(self):
        return platform.platform._disklabel_types

    @property
    def device_descriptions(self):
        return platform.platform.bootStage1ConstraintDict["descriptions"]

    #
    # constraint checking for target devices
    #
    def _is_valid_md(self, device, raid_levels=None,
                     metadata=None, member_types=None, desc=""):
        ret = True
        if device.type != "mdarray":
            return ret

        if raid_levels and device.level not in raid_levels:
            levels_str = ",".join("RAID%d" % l for l in raid_levels)
            self.errors.append(_("RAID sets that contain '%(desc)s' must have one "
                                 "of the following raid levels: %(raid_level)s.")
                                 % {"desc" : desc, "raid_level" : levels_str})
            ret = False

        # new arrays will be created with an appropriate metadata format
        if device.exists and \
           metadata and device.metadataVersion not in metadata:
            self.errors.append(_("RAID sets that contain '%(desc)s' must have one "
                                 "of the following metadata versions: %(metadata_versions)s.")
                               % {"desc": desc, "metadata_versions": ",".join(metadata)})
            ret = False

        if member_types:
            for member in device.devices:
                if not self._device_type_match(member, member_types):
                    self.errors.append(_("RAID sets that contain '%(desc)s' must "
                                         "have one of the following device "
                                         "types: %(types)s.")
                                         % {"desc" : desc, "types" : ",".join(member_types)})
                    ret = False

        log.debug("_is_valid_md(%s) returning %s", device.name, ret)
        return ret

    def _is_valid_disklabel(self, device, disklabel_types=None):
        ret = True
        if self.disklabel_types:
            for disk in device.disks:
                label_type = getattr(disk.format, "labelType", None)
                if not label_type or label_type not in self.disklabel_types:
                    types_str = ",".join(disklabel_types)
                    self.errors.append(_("%(name)s must have one of the following "
                                         "disklabel types: %(types)s.")
                                         % {"name" : device.name, "types" : types_str})
                    ret = False

        log.debug("_is_valid_disklabel(%s) returning %s", device.name, ret)
        return ret

    def _is_valid_format(self, device, format_types=None, mountpoints=None,
                         desc=""):
        ret = True
        if format_types and device.format.type not in format_types:
            self.errors.append(_("%(desc)s cannot be of type %(type)s.")
                                 % {"desc" : desc, "type" : device.format.type})
            ret = False

        if mountpoints and hasattr(device.format, "mountpoint") \
           and device.format.mountpoint not in mountpoints:
            self.errors.append(_("%(desc)s must be mounted on one of %(mountpoints)s.")
                                 % {"desc" : desc, "mountpoints" : ", ".join(mountpoints)})
            ret = False

        log.debug("_is_valid_format(%s) returning %s", device.name, ret)
        return ret

    def _is_valid_size(self, device, desc=""):
        ret = True
        msg = None
        errors = []
        if device.format.minSize and device.format.maxSize:
            msg = (_("%(desc)s must be between %(min)d and %(max)d MB in size")
                     % {"desc" : desc, "min" : device.format.minSize,
                         "max" : device.format.maxSize})

        if device.format.minSize and device.size < device.format.minSize:
            if msg is None:
                errors.append(_("%(desc)s must not be smaller than %(min)dMB.")
                                % {"desc" : desc, "min" : device.format.minSize})
            else:
                errors.append(msg)

            ret = False

        if device.format.maxSize and device.size > device.format.maxSize:
            if msg is None:
                errors.append(_("%(desc)s must not be larger than %(max)dMB.")
                                % {"desc" : desc, "max" : device.format.maxSize})
            elif msg not in errors:
                # don't add the same error string twice
                errors.append(msg)

            ret = False

        log.debug("_is_valid_size(%s) returning %s", device.name, ret)
        return ret

    def _is_valid_location(self, device, max_mb=None, desc=""):
        ret = True
        if max_mb and device.type == "partition" and device.partedPartition:
            end_sector = device.partedPartition.geometry.end
            sector_size = device.partedPartition.disk.device.sectorSize
            end_mb = (sector_size * end_sector) / (1024.0 * 1024.0)
            if end_mb > max_mb:
                self.errors.append(_("%(desc)s must be within the first %(max_mb)dMB of "
                                     "the disk.") % {"desc": desc, "max_mb": max_mb})
                ret = False

        log.debug("_is_valid_location(%s) returning %s", device.name, ret)
        return ret

    def _is_valid_partition(self, device, primary=None, desc=""):
        ret = True
        if device.type == "partition" and primary and not device.isPrimary:
            self.errors.append(_("%s must be on a primary partition.") % desc)
            ret = False

        log.debug("_is_valid_partition(%s) returning %s", device.name, ret)
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

    def is_valid_stage1_device(self, device, early=False):
        """ Return True if the device is a valid stage1 target device.

            Also collect lists of errors and warnings.

            The criteria for being a valid stage1 target device vary from
            platform to platform. On some platforms a disk with an msdos
            disklabel is a valid stage1 target, while some platforms require
            a special device. Some examples of these special devices are EFI
            system partitions on EFI machines, PReP boot partitions on
            iSeries, and Apple bootstrap partitions on Mac.

            The 'early' keyword argument is a boolean flag indicating whether
            or not this check is being performed at a point where the mountpoint
            cannot be expected to be set for things like EFI system partitions.
        """
        self.errors = []
        self.warnings = []
        valid = True
        constraint = platform.platform.bootStage1ConstraintDict

        if device is None:
            return False

        if not self._device_type_match(device, constraint["device_types"]):
            log.debug("stage1 device cannot be of type %s", device.type)
            return False

        description = self.device_description(device)

        if self.stage2_is_valid_stage1 and device == self.stage2_device:
            # special case
            valid = (self.stage2_is_preferred_stage1 and
                     self.is_valid_stage2_device(device))

            # we'll be checking stage2 separately so don't duplicate messages
            self.problems = []
            self.warnings = []
            return valid

        if device.protected:
            valid = False

        if not self._is_valid_disklabel(device,
                                        disklabel_types=self.disklabel_types):
            valid = False

        if not self._is_valid_size(device, desc=description):
            valid = False

        if not self._is_valid_location(device,
                                       max_mb=constraint["max_end_mb"],
                                       desc=description):
            valid = False

        if not self._is_valid_md(device,
                                 raid_levels=constraint["raid_levels"],
                                 metadata=constraint["raid_metadata"],
                                 member_types=constraint["raid_member_types"],
                                 desc=description):
            valid = False

        if not self.stage2_bootable and not getattr(device, "bootable", True):
            log.warning("%s not bootable", device.name)

        # XXX does this need to be here?
        if getattr(device.format, "label", None) in ("ANACONDA", "LIVE"):
            log.info("ignoring anaconda boot disk")
            valid = False

        if early:
            mountpoints = []
        else:
            mountpoints = constraint["mountpoints"]

        if not self._is_valid_format(device,
                                     format_types=constraint["format_types"],
                                     mountpoints=mountpoints,
                                     desc=description):
            valid = False

        if not self.encryption_support and device.encrypted:
            self.errors.append(_("%s cannot be on an encrypted block "
                                 "device.") % description)
            valid = False

        log.debug("is_valid_stage1_device(%s) returning %s", device.name, valid)
        return valid

    def set_stage1_device(self, devices):
        self.stage1_device = None
        if not self.stage1_disk:
            self.reset()
            raise BootLoaderError("need stage1 disk to set stage1 device")

        if self.stage2_is_preferred_stage1:
            self.stage1_device = self.stage2_device
            return

        for device in devices:
            if self.stage1_disk not in device.disks:
                continue

            if self.is_valid_stage1_device(device):
                if flags.imageInstall and device.isDisk:
                    # GRUB2 will install to /dev/loop0 but not to
                    # /dev/mapper/<image_name>
                    self.stage1_device = device.parents[0]
                else:
                    self.stage1_device = device

                break

        if not self.stage1_device:
            self.reset()
            raise BootLoaderError("failed to find a suitable stage1 device")

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

        if device.protected:
            valid = False

        if not self._device_type_match(device, self.stage2_device_types):
            self.errors.append(_("%(desc)s cannot be of type %(type)s")
                                 % {"desc" : self.stage2_description, "type" : device.type})
            valid = False

        if not self._is_valid_disklabel(device,
                                        disklabel_types=self.disklabel_types):
            valid = False

        if not self._is_valid_size(device, desc=self.stage2_description):
            valid = False

        if not self._is_valid_location(device,
                                       max_mb=self.stage2_max_end_mb,
                                       desc=self.stage2_description):
            valid = False

        if not self._is_valid_partition(device,
                                        primary=self.stage2_must_be_primary):
            valid = False

        if not self._is_valid_md(device,
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

        non_linux_format_types = platform.platform._non_linux_format_types
        if non_linux and \
           not self._is_valid_format(device,
                                     format_types=non_linux_format_types):
            valid = False

        if not self.encryption_support and device.encrypted:
            self.errors.append(_("%s cannot be on an encrypted block "
                                 "device.") % self.stage2_description)
            valid = False

        log.debug("is_valid_stage2_device(%s) returning %s", device.name, valid)
        return valid

    #
    # miscellaneous
    #

    def has_windows(self, devices):
        return False

    # pylint: disable-msg=E0202
    @property
    def timeout(self):
        """Bootloader timeout in seconds."""
        if self._timeout is not None:
            t = self._timeout
        else:
            t = 5

        return t

    def check(self):
        """ Run additional bootloader checks """
        return True

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

                storage - a blivet.Storage instance

            All other arguments are expected to have a dracutSetupArgs()
            method.
        """
        storage = kwargs.pop("storage", None)

        #
        # FIPS
        #
        if flags.cmdline.get("fips") == "1":
            self.boot_args.add("boot=%s" % self.stage2_device.fstabSpec)

        #
        # dracut
        #

        # storage
        from blivet.devices import NetworkStorageDevice
        dracut_devices = [storage.rootDevice]
        if self.stage2_device != storage.rootDevice:
            dracut_devices.append(self.stage2_device)

        dracut_devices.extend(storage.fsset.swapDevices)

        # Does /usr have its own device? If so, we need to tell dracut
        usr_device = storage.mountpoints.get("/usr")
        if usr_device:
            dracut_devices.extend([usr_device])

        done = []
        for device in dracut_devices:
            for dep in storage.devices:
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

                # network storage
                # XXX this is nothing to be proud of
                if isinstance(dep, NetworkStorageDevice):
                    setup_args = pyanaconda.network.dracutSetupArgs(dep)
                    self.boot_args.update(setup_args)
                    self.dracut_args.update(setup_args)

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

        # This is needed for FCoE, bug #743784. The case:
        # We discover LUN on an iface which is part of multipath setup.
        # If the iface is disconnected after discovery anaconda doesn't
        # write dracut ifname argument for the disconnected iface path
        # (in Network.dracutSetupArgs).
        # Dracut needs the explicit ifname= because biosdevname
        # fails to rename the iface (because of BFS booting from it).
        for nic, _dcb, _auto_vlan in fcoe().nics:
            try:
                hwaddr = nm_device_hwaddress(nic)
            except ValueError:
                continue
            self.boot_args.add("ifname=%s:%s" % (nic, hwaddr.lower()))

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
        if self.stage2_device.format.mountpoint == "/":
            prefix = "/boot"
        else:
            prefix = ""

        return prefix

    def _set_console(self):
        """ Set console options based on boot arguments. """
        console = flags.cmdline.get("console", "")
        console = os.path.basename(console)
        self.console, _x, self.console_options = console.partition(",")

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
        raise NotImplementedError()

    def write_config_post(self):
        try:
            os.chmod(ROOT_PATH + self.config_file, self.config_file_mode)
        except OSError as e:
            log.error("failed to set config file permissions: %s", e)

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
        if self.skip_bootloader:
            return

        if self.update_only:
            self.update()
            return

        self.write_config()
        sync()
        self.stage2_device.format.sync(root=ROOT_PATH)
        self.install()

    def install(self, args=None):
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
    stage2_must_be_primary = False

    # list of strings representing options for boot device types
    stage2_device_types = ["partition", "mdarray"]
    stage2_raid_levels = [mdraid.RAID1]
    stage2_raid_member_types = ["partition"]
    stage2_raid_metadata = ["0", "0.90", "1.0"]

    packages = ["grub"]

    def __init__(self):
        super(GRUB, self).__init__()
        self.encrypted_password = ""

    #
    # grub-related conveniences
    #

    def grub_device_name(self, device):
        """ Return a grub-friendly representation of device. """
        disk = getattr(device, "disk", device)
        name = "(hd%d" % self.disks.index(disk)
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
    def splash_dir(self):
        """ relative path to splash image directory."""
        return GRUB._config_dir

    @property
    def serial_command(self):
        command = ""
        if self.console and self.console.startswith("ttyS"):
            unit = self.console[-1]
            command = ["serial"]
            s = parse_serial_opt(self.console_options)
            if unit and unit != '0':
                command.append("--unit=%s" % unit)
            if s.speed and s.speed != '9600':
                command.append("--speed=%s" % s.speed)
            if s.parity:
                if s.parity == 'o':
                    command.append("--parity=odd")
                elif s.parity == 'e':
                    command.append("--parity=even")
            if s.word and s.word != '8':
                command.append("--word=%s" % s.word)
            if s.stop and s.stop != '1':
                command.append("--stop=%s" % s.stop)
            command = " ".join(command)
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
        salt += "".join(rand_gen.choice(salt_chars) for i in range(salt_len))
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

        if iutil.isConsoleOnVirtualTerminal(self.console):
            splash = "splash.xpm.gz"
            splash_path = os.path.normpath("%s/boot/%s/%s" % (ROOT_PATH,
                                                        self.splash_dir,
                                                        splash))
            if os.access(splash_path, os.R_OK):
                grub_root_grub_name = self.grub_device_name(self.stage2_device)
                config.write("splashimage=%s/%s/%s\n" % (grub_root_grub_name,
                                                         self.splash_dir,
                                                         splash))
                config.write("hiddenmenu\n")

        self.write_config_password(config)

    def write_config_images(self, config):
        """ Write image entries into configuration file. """
        for image in self.images:
            args = Arguments()
            if isinstance(image, LinuxBootLoaderImage):
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

            log.info("bootloader.py: used boot args: %s ", args)
            config.write(stanza)

    def write_device_map(self):
        """ Write out a device map containing all supported devices. """
        map_path = os.path.normpath(ROOT_PATH + self.device_map_file)
        if os.access(map_path, os.R_OK):
            os.rename(map_path, map_path + ".anacbak")

        dev_map = open(map_path, "w")
        dev_map.write("# this device map was generated by anaconda\n")
        for disk in self.disks:
            dev_map.write("%s      %s\n" % (self.grub_device_name(disk),
                                            disk.path))
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
                log.error("failed to back up %s: %s", menu_lst, e)

        try:
            os.symlink(self._config_file, menu_lst)
        except OSError as e:
            log.error("failed to create grub menu.lst symlink: %s", e)

        # make symlink to grub.conf in /etc since that's where configs belong
        etc_grub = "%s/etc/%s" % (ROOT_PATH, self._config_file)
        if os.access(etc_grub, os.R_OK):
            try:
                os.unlink(etc_grub)
            except OSError as e:
                log.error("failed to remove %s: %s", etc_grub, e)

        try:
            os.symlink("..%s" % self.config_file, etc_grub)
        except OSError as e:
            log.error("failed to create /etc/grub.conf symlink: %s", e)

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

    def install(self, args=None):
        rc = iutil.execWithRedirect("grub-install", ["--just-copy"],
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
                      "stage1dev": self.grub_device_name(stage1dev),
                      "stage2dev": self.grub_device_name(stage2dev)})
            (pread, pwrite) = os.pipe()
            os.write(pwrite, cmd)
            os.close(pwrite)
            args = ["--batch", "--no-floppy",
                    "--device-map=%s" % self.device_map_file]
            rc = iutil.execWithRedirect("grub", args,
                                        stdin=pread, root=ROOT_PATH)
            os.close(pread)
            if rc:
                raise BootLoaderError("bootloader install failed")

    def update(self):
        self.install()

    #
    # miscellaneous
    #

    def has_windows(self, devices):
        """ Potential boot devices containing non-linux operating systems. """
        # make sure we don't clobber error/warning lists
        errors = self.errors[:]
        warnings = self.warnings[:]
        ret = [d for d in devices if self.is_valid_stage2_device(d, linux=False, non_linux=True)]
        self.errors = errors
        self.warnings = warnings
        return bool(ret)

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
    packages = ["grub2"]
    _config_file = "grub.cfg"
    _config_dir = "grub2"
    config_file_mode = 0600
    defaults_file = "/etc/default/grub"
    can_dual_boot = True
    can_update = True
    terminal_type = "console"

    # requirements for boot devices
    stage2_device_types = ["partition", "mdarray", "lvmlv", "btrfs volume",
                           "btrfs subvolume"]
    stage2_raid_levels = [mdraid.RAID0, mdraid.RAID1, mdraid.RAID4,
                          mdraid.RAID5, mdraid.RAID6, mdraid.RAID10]
    stage2_raid_metadata = ["0", "0.90", "1.0", "1.2"]

    @property
    def stage2_format_types(self):
        if productName.startswith("Red Hat Enterprise Linux"):
            return ["xfs", "ext4", "ext3", "ext2", "btrfs"]
        else:
            return ["ext4", "ext3", "ext2", "btrfs", "xfs"]

    def __init__(self):
        super(GRUB2, self).__init__()
        self.boot_args.add("$([ -x /usr/sbin/rhcrashkernel-param ] && "\
                           "/usr/sbin/rhcrashkernel-param || :)")

    # XXX we probably need special handling for raid stage1 w/ gpt disklabel
    #     since it's unlikely there'll be a bios boot partition on each disk

    #
    # grub-related conveniences
    #

    def grub_device_name(self, device):
        """ Return a grub-friendly representation of device.

            Disks and partitions use the (hdX,Y) notation, while lvm and
            md devices just use their names.
        """
        disk = None
        name = "(%s)" % device.name

        if device.isDisk:
            disk = device
        elif hasattr(device, "disk"):
            disk = device.disk

        if disk is not None:
            name = "(hd%d" % self.disks.index(disk)
            if hasattr(device, "disk"):
                lt = device.disk.format.labelType
                name += ",%s%d" % (lt, device.partedPartition.number)
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

        devices = self.disks
        if self.stage1_device not in devices:
            devices.append(self.stage1_device)

        for disk in self.stage2_device.disks:
            if disk not in devices:
                devices.append(disk)

        devices = [d for d in devices if d.isDisk]

        if len(devices) == 0:
            return

        dev_map = open(map_path, "w")
        dev_map.write("# this device map was generated by anaconda\n")
        for drive in devices:
            dev_map.write("%s      %s\n" % (self.grub_device_name(drive),
                                            drive.path))
        dev_map.close()

    def write_defaults(self):
        defaults_file = "%s%s" % (ROOT_PATH, self.defaults_file)
        defaults = open(defaults_file, "w+")
        defaults.write("GRUB_TIMEOUT=%d\n" % self.timeout)
        defaults.write("GRUB_DISTRIBUTOR=\"$(sed 's, release .*$,,g' /etc/system-release)\"\n")
        defaults.write("GRUB_DEFAULT=saved\n")
        defaults.write("GRUB_DISABLE_SUBMENU=true\n")
        if self.console and self.console.startswith("ttyS"):
            defaults.write("GRUB_TERMINAL=\"serial console\"\n")
            defaults.write("GRUB_SERIAL_COMMAND=\"%s\"\n" % self.serial_command)
        else:
            defaults.write("GRUB_TERMINAL_OUTPUT=\"%s\"\n" % self.terminal_type)

        # this is going to cause problems for systems containing multiple
        # linux installations or even multiple boot entries with different
        # boot arguments
        log.info("bootloader.py: used boot args: %s ", self.boot_args)
        defaults.write("GRUB_CMDLINE_LINUX=\"%s\"\n" % self.boot_args)
        defaults.write("GRUB_DISABLE_RECOVERY=\"true\"\n")
        #defaults.write("GRUB_THEME=\"/boot/grub2/themes/system/theme.txt\"\n")
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
        header.write("export superusers\n")
        self._encrypt_password()
        password_line = "password_pbkdf2 root " + self.encrypted_password
        header.write("%s\n" % password_line)
        header.write("EOF\n")
        header.close()
        os.chmod(users_file, 0700)

    def write_config(self):
        self.write_config_console(None)
        # See if we have a password and if so update the boot args before we
        # write out the defaults file.
        if self.password or self.encrypted_password:
            self.boot_args.add("rd.shell=0")
        self.write_defaults()

        # if we fail to setup password auth we should complete the
        # installation so the system is at least bootable
        try:
            self.write_password_config()
        except (BootLoaderError, OSError, RuntimeError) as e:
            log.error("bootloader password setup failed: %s", e)

        # make sure the default entry is the OS we are installing
        entry_title = "%s Linux, with Linux %s" % (productName,
                                                   self.default.version)
        rc = iutil.execWithRedirect("grub2-set-default",
                                    [entry_title],
                                    root=ROOT_PATH)
        if rc:
            log.error("failed to set default menu entry to %s", productName)

        # now tell grub2 to generate the main configuration file
        rc = iutil.execWithRedirect("grub2-mkconfig",
                                    ["-o", self.config_file],
                                    root=ROOT_PATH)
        if rc:
            raise BootLoaderError("failed to write bootloader configuration")

    #
    # installation
    #

    def install(self, args=None):
        if args is None:
            args = []

        # XXX will installing to multiple drives work as expected with GRUBv2?
        for (stage1dev, stage2dev) in self.install_targets:
            grub_args = args + ["--no-floppy", stage1dev.path]
            if stage1dev == stage2dev:
                # This is hopefully a temporary hack. GRUB2 currently refuses
                # to install to a partition's boot block without --force.
                grub_args.insert(0, '--force')

            rc = iutil.execWithRedirect("grub2-install", grub_args,
                                        root=ROOT_PATH,
                                        env_prune=['MALLOC_PERTURB_'])
            if rc:
                raise BootLoaderError("bootloader install failed")

    def write(self):
        """ Write the bootloader configuration and install the bootloader. """
        if self.skip_bootloader:
            return

        if self.update_only:
            self.update()
            return

        self.write_device_map()
        self.stage2_device.format.sync(root=ROOT_PATH)
        sync()
        self.install()
        sync()
        self.stage2_device.format.sync(root=ROOT_PATH)
        self.write_config()
        sync()
        self.stage2_device.format.sync(root=ROOT_PATH)

    def check(self):
        """ When installing to the mbr of a disk grub2 needs enough space
        before the first partition in order to embed its core.img

        Until we have a way to ask grub2 what the size is we check to make
        sure it starts >= 512K, otherwise return an error.
        """
        ret = True
        base_gap_bytes = 32256      # 31.5KiB
        advanced_gap_bytes = 524288 # 512KiB
        self.errors = []
        self.warnings = []

        if self.stage1_device == self.stage2_device:
            return ret

        # These are small enough to fit
        if self.stage2_device.type == "partition":
            min_start = base_gap_bytes
        else:
            min_start = advanced_gap_bytes

        if not self.stage1_disk:
            return False

        # If the first partition starts too low show an error.
        parts = self.stage1_disk.format.partedDisk.partitions
        for p in parts:
            start = p.geometry.start * p.disk.device.sectorSize
            if not p.getFlag(PARTITION_BIOS_GRUB) and start < min_start:
                msg = _("%(deviceName)s may not have enough space for grub2 to embed "
                        "core.img when using the %(fsType)s filesystem on %(deviceType)s") \
                        % {"deviceName": self.stage1_device.name, "fsType": self.stage2_device.format.type,
                           "deviceType": self.stage2_device.type}
                log.error(msg)
                self.errors.append(msg)
                ret = False
                break

        return ret

class EFIGRUB(GRUB2):
    packages = ["grub2-efi", "efibootmgr", "shim"]
    can_dual_boot = False
    stage2_is_valid_stage1 = False
    stage2_bootable = False

    @property
    def _config_dir(self):
        return "efi/EFI/%s" % (self.efi_dir,)

    def __init__(self):
        super(EFIGRUB, self).__init__()
        self.efi_dir = 'BOOT'

    def efibootmgr(self, *args, **kwargs):
        if kwargs.pop("capture", False):
            exec_func = iutil.execWithCapture
        else:
            exec_func = iutil.execWithRedirect

        return exec_func("efibootmgr", list(args), **kwargs)

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
                # slot_id is hex, we can't use .isint and use this regex:
                if not re.match("^[0-9a-fA-F]+$", slot_id):
                    log.warning("failed to parse efi boot slot (%s)", slot)
                    continue

                rc = self.efibootmgr("-b", slot_id, "-B",
                                     root=ROOT_PATH)
                if rc:
                    raise BootLoaderError("failed to remove old efi boot entry")

    @property
    def efi_dir_as_efifs_dir(self):
        ret = self._config_dir.replace('efi/', '')
        return "\\" + ret.replace('/', '\\')

    def add_efi_boot_target(self):
        if self.stage1_device.type == "partition":
            boot_disk = self.stage1_device.disk
            boot_part_num = self.stage1_device.partedPartition.number
        elif self.stage1_device.type == "mdarray":
            # FIXME: I'm just guessing here. This probably needs the full
            #        treatment, ie: multiple targets for each member.
            boot_disk = self.stage1_device.parents[0].disk
            boot_part_num = self.stage1_device.parents[0].partedPartition.number
        boot_part_num = str(boot_part_num)

        rc = self.efibootmgr("-c", "-w", "-L", productName,
                             "-d", boot_disk.path, "-p", boot_part_num,
                             "-l",
                             self.efi_dir_as_efifs_dir + "\\shim.efi",
                             root=ROOT_PATH)
        if rc:
            raise BootLoaderError("failed to set new efi boot target")

    def install(self, args=None):
        if not flags.leavebootorder:
            self.remove_efi_boot_target()
        self.add_efi_boot_target()

    def update(self):
        self.install()

    #
    # installation
    #
    def write(self):
        """ Write the bootloader configuration and install the bootloader. """
        if self.skip_bootloader:
            return

        if self.update_only:
            self.update()
            return

        sync()
        self.stage2_device.format.sync(root=ROOT_PATH)
        self.install()
        self.write_config()

    def check(self):
        return True

class MacEFIGRUB(EFIGRUB):
    def mactel_config(self):
        if os.path.exists(ROOT_PATH + "/usr/libexec/mactel-boot-setup"):
            rc = iutil.execWithRedirect("/usr/libexec/mactel-boot-setup", [],
                                        root=ROOT_PATH)
            if rc:
                log.error("failed to configure Mac bootloader")

    def install(self, args=None):
        super(MacEFIGRUB, self).install()
        self.mactel_config()


class YabootBase(BootLoader):
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
            if self.password:
                args.add("rd.shell=0")
            if image.initrd:
                initrd_line = "\tinitrd=%s/%s\n" % (self.boot_prefix,
                                                    image.initrd)
            else:
                initrd_line = ""

            root_device_spec = image.device.fstabSpec
            if root_device_spec.startswith("/"):
                root_line = "\troot=%s\n" % root_device_spec
            else:
                args.add("root=%s" % root_device_spec)
                root_line = ""

            args.update(self.boot_args)
            log.info("bootloader.py: used boot args: %s ", args)

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


class Yaboot(YabootBase):
    name = "Yaboot"
    _config_file = "yaboot.conf"
    prog = "ybin"
    image_label_attr = "short_label"
    packages = ["yaboot"]

    # stage2 device requirements
    stage2_device_types = ["partition", "mdarray"]
    stage2_device_raid_levels = [mdraid.RAID1]

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
                log.error("failed to create /etc/yaboot.conf symlink: %s", e)

    def write_config(self):
        if not os.path.isdir(ROOT_PATH + self.config_dir):
            os.mkdir(ROOT_PATH + self.config_dir)

        # this writes the config
        super(Yaboot, self).write_config()

    #
    # installation
    #

    def install(self, args=None):
        args = ["-f", "-C", self.config_file]
        rc = iutil.execWithRedirect(self.prog, args,
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

    #
    # installation
    #

    def install(self, args=None):
        self.updatePowerPCBootList()

        super(IPSeriesYaboot, self).install()

    def updatePowerPCBootList(self):

        log.debug("updatePowerPCBootList: self.stage1_device.path = %s", self.stage1_device.path)

        buf = iutil.execWithCapture("nvram",
                                    ["--print-config=boot-device"])

        if len(buf) == 0:
            log.error ("FAIL: nvram --print-config=boot-device")
            return

        boot_list = buf.strip().split()
        log.debug("updatePowerPCBootList: boot_list = %s", boot_list)

        buf = iutil.execWithCapture("ofpathname",
                                    [self.stage1_device.path])

        if len(buf) > 0:
            boot_disk = buf.strip()
            log.debug("updatePowerPCBootList: boot_disk = %s", boot_disk)
        else:
            log.error("FAIL: ofpathname %s", self.stage1_device.path)
            return

        # Place the disk containing the PReP partition first.
        # Remove all other occurances of it.
        boot_list = [boot_disk] + filter(lambda x: x != boot_disk, boot_list)

        log.debug("updatePowerPCBootList: updated boot_list = %s", boot_list)

        update_value = "boot-device=%s" % " ".join(boot_list)

        rc = iutil.execWithRedirect("nvram", ["--update-config", update_value])
        if rc:
            log.error("FAIL: nvram --update-config %s", update_value)
        else:
            log.info("Updated PPC boot list with the command: nvram --update-config %s", update_value)


class IPSeriesGRUB2(GRUB2):

    # GRUB2 sets /boot bootable and not the PReP partition.  This causes the Open Firmware BIOS not
    # to present the disk as a bootable target.  If stage2_bootable is False, then the PReP partition
    # will be marked bootable. Confusing.
    stage2_bootable = False
    terminal_type = "ofconsole"

    #
    # installation
    #

    def install(self, args=None):
        if flags.leavebootorder:
            log.info("leavebootorder passed as an option. Will not update the NVRAM boot list.")
        else:
            self.updateNVRAMBootList()

        super(IPSeriesGRUB2, self).install(args=["--no-nvram"])

    # This will update the PowerPC's (ppc) bios boot devive order list
    def updateNVRAMBootList(self):

        log.debug("updateNVRAMBootList: self.stage1_device.path = %s", self.stage1_device.path)

        buf = iutil.execWithCapture("nvram",
                                    ["--print-config=boot-device"])

        if len(buf) == 0:
            log.error ("Failed to determine nvram boot device")
            return

        boot_list = buf.strip().replace("\"", "").split()
        log.debug("updateNVRAMBootList: boot_list = %s", boot_list)

        buf = iutil.execWithCapture("ofpathname",
                                    [self.stage1_device.path])

        if len(buf) > 0:
            boot_disk = buf.strip()
        else:
            log.error("Failed to translate boot path into device name")
            return

        # Place the disk containing the PReP partition first.
        # Remove all other occurances of it.
        boot_list = [boot_disk] + filter(lambda x: x != boot_disk, boot_list)

        update_value = "boot-device=%s" % " ".join(boot_list)

        rc = iutil.execWithRedirect("nvram", ["--update-config", update_value])
        if rc:
            log.error("Failed to update new boot device order")

    #
    # In addition to the normal grub configuration variable, add one more to set the size of the
    # console's window to a standard 80x24
    #
    def write_defaults(self):
        super(IPSeriesGRUB2, self).write_defaults()

        defaults_file = "%s%s" % (ROOT_PATH, self.defaults_file)
        defaults = open(defaults_file, "a+")
        # The terminfo's X and Y size, and output location could change in the future
        defaults.write("GRUB_TERMINFO=\"terminfo -g 80x24 console\"\n")
        defaults.close()


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

    @property
    def stage2_format_types(self):
        if productName.startswith("Red Hat Enterprise Linux"):
            return ["xfs", "ext4", "ext3", "ext2"]
        else:
            return ["ext4", "ext3", "ext2", "xfs"]

    image_label_attr = "short_label"
    preserve_args = ["cio_ignore"]

    def __init__(self):
        super(ZIPL, self).__init__()
        self.stage1_name = None

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
            args.add("root=%s" % image.device.fstabSpec)
            args.update(self.boot_args)
            log.info("bootloader.py: used boot args: %s ", args)
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
                  "defaultauto\n"
                  "prompt=1\n"
                  "timeout=%(timeout)d\n"
                  "default=%(default)s\n"
                  "target=/boot\n"
                  % {"timeout": self.timeout,
                     "default": self.image_label(self.default)})
        config.write(header)

    #
    # installation
    #

    def install(self, args=None):
        buf = iutil.execWithCapture("zipl", [], root=ROOT_PATH)
        for line in buf.splitlines():
            if line.startswith("Preparing boot device: "):
                # Output here may look like:
                #     Preparing boot device: dasdb (0200).
                #     Preparing boot device: dasdl.
                # We want to extract the device name and pass that.
                name = re.sub(r".+?: ", "", line)
                self.stage1_name = re.sub(r"(\s\(.+\))?\.$", "", name)

        if not self.stage1_name:
            raise BootLoaderError("could not find IPL device")

        # do the reipl
        iutil.reIPL(self.stage1_name)

class EXTLINUX(BootLoader):
    name = "EXTLINUX"
    _config_file = "extlinux.conf"
    _config_dir = "/boot/extlinux"

    # stage1 device requirements
    stage1_device_types = ["disk"]

    # stage2 device requirements
    stage2_format_types = ["ext4", "ext3", "ext2"]
    stage2_device_types = ["partition"]
    stage2_bootable = True

    packages = ["syslinux-extlinux"]

    @property
    def config_file(self):
        return "%s/%s" % (self._config_dir, self._config_file)

    @property
    def boot_prefix(self):
        """ Prefix, if any, to paths in /boot. """
        if self.stage2_device.format.mountpoint == "/":
            prefix = "/boot"
        else:
            prefix = ""

        return prefix

    def write_config_console(self, config):
        if not self.console:
            return

        console_arg = "console=%s" % self.console
        if self.console_options:
            console_arg += ",%s" % self.console_options
        self.boot_args.add(console_arg)

    def write_config_images(self, config):
        self.write_config_console(config)
        for image in self.images:
            args = Arguments()
            args.add("root=%s" % image.device.fstabSpec)
            args.update(self.boot_args)
            log.info("bootloader.py: used boot args: %s ", args)
            stanza = ("label %(label)s (%(version)s)\n"
                      "\tkernel %(boot_prefix)s/%(kernel)s\n"
                      "\tinitrd %(boot_prefix)s/%(initrd)s\n"
                      "\tappend %(args)s\n\n"
                      % {"label": self.image_label(image),
                         "version": image.version,
                         "kernel": image.kernel,
                         "initrd": image.initrd,
                         "args": args,
                         "boot_prefix": self.boot_prefix})
            config.write(stanza)

    def write_config_header(self, config):
        header = ("# extlinux.conf generated by anaconda\n\n"
                  "ui menu.c32\n\n"
                  "menu autoboot Welcome to %(productName)s. Automatic boot in # second{,s}. Press a key for options.\n"
                  "menu title %(productName)s Boot Options.\n"
                  "menu hidden\n\n"
                  "timeout %(timeout)d\n"
                  "#totaltimeout 9000\n\n"
                  "default %(default)s\n\n"
                  % { "productName": productName, "timeout": self.timeout *10,
                     "default": self.image_label(self.default)})
        config.write(header)
        self.write_config_password(config)

    def write_config_password(self, config):
        if self.password:
            config.write("menu master passwd %s\n" % self.password)
            config.write("menu notabmsg Press [Tab] and enter the password to edit options")

    def write_config_post(self):
        etc_extlinux = os.path.normpath(ROOT_PATH + "/etc/" + self._config_file)
        if not os.access(etc_extlinux, os.R_OK):
            try:
                os.symlink("../boot/%s" % self._config_file, etc_extlinux)
            except OSError as e:
                log.warning("failed to create /etc/extlinux.conf symlink: %s", e)

    def write_config(self):
        super(EXTLINUX, self).write_config()

    #
    # installation
    #

    def install(self, args=None):
        args = ["--install", self._config_dir]
        rc = iutil.execWithRedirect("extlinux", args,
                                    root=ROOT_PATH)

        if rc:
            raise BootLoaderError("bootloader install failed")


# every platform that wants a bootloader needs to be in this dict
bootloader_by_platform = {platform.X86: GRUB2,
                          platform.EFI: EFIGRUB,
                          platform.MacEFI: MacEFIGRUB,
                          platform.PPC: GRUB2,
                          platform.IPSeriesPPC: IPSeriesGRUB2,
                          platform.NewWorldPPC: MacYaboot,
                          platform.S390: ZIPL,
                          platform.ARM: EXTLINUX,
                          platform.omapARM: EXTLINUX}

def get_bootloader():
    platform_name = platform.platform.__class__.__name__
    if flags.extlinux:
        cls = EXTLINUX
    else:
        cls = bootloader_by_platform.get(platform.platform.__class__, BootLoader)
    log.info("bootloader %s on %s platform", cls.__name__, platform_name)
    return cls()


# anaconda-specific functions

def writeSysconfigKernel(storage, version):
    # get the name of the default kernel package based on the version
    kernel_basename = "vmlinuz-" + version
    kernel_file = "/boot/%s" % kernel_basename
    if not os.path.isfile(ROOT_PATH + kernel_file):
        kernel_file = "/boot/efi/EFI/redhat/%s" % kernel_basename
        if not os.path.isfile(ROOT_PATH + kernel_file):
            log.error("failed to recreate path to default kernel image")
            return

    try:
        import rpm
    except ImportError:
        log.error("failed to import rpm python module")
        return

    ts = rpm.TransactionSet(ROOT_PATH)
    mi = ts.dbMatch('basenames', kernel_file)
    try:
        h = mi.next()
    except StopIteration:
        log.error("failed to get package name for default kernel")
        return

    kernel = h.name

    f = open(ROOT_PATH + "/etc/sysconfig/kernel", "w+")
    f.write("# UPDATEDEFAULT specifies if new-kernel-pkg should make\n"
            "# new kernels the default\n")
    # only update the default if we're setting the default to linux (#156678)
    if storage.bootloader.default.device == storage.rootDevice:
        f.write("UPDATEDEFAULT=yes\n")
    else:
        f.write("UPDATEDEFAULT=no\n")
    f.write("\n")
    f.write("# DEFAULTKERNEL specifies the default kernel package type\n")
    f.write("DEFAULTKERNEL=%s\n" % kernel)
    if storage.bootloader.trusted_boot:
        f.write("# HYPERVISOR specifies the default multiboot kernel\n")
        f.write("HYPERVISOR=/boot/tboot.gz\n")
        f.write("HYPERVISOR_ARGS=logging=vga,serial,memory\n")
    f.close()

def writeBootLoader(storage, payload, instClass, ksdata):
    """ Write bootloader configuration to disk.

        When we get here, the bootloader will already have a default linux
        image. We only have to add images for the non-default kernels and
        adjust the default to reflect whatever the default variant is.
    """
    from pyanaconda.errors import errorHandler, ERROR_RAISE

    if not storage.bootloader.skip_bootloader:
        stage1_device = storage.bootloader.stage1_device
        log.info("bootloader stage1 target device is %s", stage1_device.name)
        stage2_device = storage.bootloader.stage2_device
        log.info("bootloader stage2 target device is %s", stage2_device.name)

    # get a list of installed kernel packages
    kernel_versions = payload.kernelVersionList
    if not kernel_versions:
        log.warning("no kernel was installed -- bootloader config unchanged")
        return

    # all the linux images' labels are based on the default image's
    base_label = productName
    base_short_label = "linux"

    # The first one is the default kernel. Update the bootloader's default
    # entry to reflect the details of the default kernel.
    version = kernel_versions.pop(0)
    default_image = LinuxBootLoaderImage(device=storage.rootDevice,
                                         version=version,
                                         label=base_label,
                                         short=base_short_label)
    storage.bootloader.add_image(default_image)
    storage.bootloader.default = default_image
    if hasattr(storage.bootloader, 'efi_dir'):
        storage.bootloader.efi_dir = instClass.efi_dir

    # write out /etc/sysconfig/kernel
    writeSysconfigKernel(storage, version)

    if storage.bootloader.skip_bootloader:
        log.info("skipping bootloader install per user request")
        return

    # now add an image for each of the other kernels
    for version in kernel_versions:
        label = "%s-%s" % (base_label, version)
        short = "%s-%s" % (base_short_label, version)
        if storage.bootloader.trusted_boot:
            image = TbootLinuxBootLoaderImage(
                                         device=storage.rootDevice,
                                         version=version,
                                         label=label, short=short)
        else:
            image = LinuxBootLoaderImage(device=storage.rootDevice,
                                         version=version,
                                         label=label, short=short)
        storage.bootloader.add_image(image)

    # set up dracut/fips boot args
    # XXX FIXME: do this from elsewhere?
    #storage.bootloader.set_boot_args(keyboard=anaconda.keyboard,
    #                                 storage=anaconda.storage,
    #                                 language=anaconda.instLanguage,
    #                                 network=anaconda.network)
    storage.bootloader.set_boot_args(storage=storage,
                                     payload=payload,
                                     keyboard=ksdata.keyboard)

    try:
        storage.bootloader.write()
    except BootLoaderError as e:
        if errorHandler.cb(e) == ERROR_RAISE:
            raise

