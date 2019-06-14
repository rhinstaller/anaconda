#
# Copyright (C) 2019 Red Hat, Inc.
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
import collections
import os
from glob import glob

import blivet
from blivet.devices import NetworkStorageDevice
from blivet.formats.disklabel import DiskLabel
from blivet.size import Size
from ordered_set import OrderedSet

from pyanaconda.network import ibft_iface, iface_for_host_ip
from pyanaconda import platform
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.bootloader.image import LinuxBootLoaderImage
from pyanaconda.core import util
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.i18n import N_, _
from pyanaconda.flags import flags
from pyanaconda.modules.common.constants.objects import FCOE, ISCSI
from pyanaconda.modules.common.structures.iscsi import Node
from pyanaconda.modules.common.constants.services import STORAGE, NETWORK
from pyanaconda.modules.common.structures.network import NetworkDeviceInfo

log = get_module_logger(__name__)

__all__ = ["BootLoaderError", "Arguments", "BootLoader"]


def _is_on_sw_iscsi(device):
    """Tells whether a given device is on an software iSCSI disk."""
    return all(isinstance(disk, blivet.devices.iScsiDiskDevice)
               and not disk.offload
               for disk in device.disks)


def _get_iscsi_node_from_device(device):
    node = Node()
    node.name = device.target
    node.address = device.address
    node.port = device.port
    node.iface = device.iface
    return node


def _is_on_ibft(device):
    """Tells whether a given device is ibft disk or not."""
    iscsi_proxy = STORAGE.get_proxy(ISCSI)
    for disk in device.disks:
        if not isinstance(disk, blivet.devices.iScsiDiskDevice):
            return False
        node = _get_iscsi_node_from_device(disk)
        if not iscsi_proxy.IsNodeFromIbft(Node.to_structure(node)):
            return False
    return True


class BootLoaderError(Exception):
    """An exception for boot loader errors."""
    pass


class Arguments(OrderedSet):
    """An ordered set of arguments."""

    def _merge_ip(self):
        """Find ip= arguments targeting the same interface and merge them."""

        # partition the input
        def partition_p(arg):
            # we are only interested in ip= parameters that use some kind of
            # automatic network setup:
            return arg.startswith("ip=") and arg.count(":") == 1

        ip_params = filter(partition_p, self)
        rest = OrderedSet(filter(lambda p: not partition_p(p), self))

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
        return " ".join(list(self))

    def add(self, key):
        self.discard(key)
        super().add(key)

    def update(self, sequence):
        for key in sequence:
            self.discard(key)
            self.add(key)


class BootLoader(object):
    """A base class for boot loaders."""

    name = "Generic Bootloader"
    packages = []
    config_file = None
    config_file_mode = 0o600
    can_dual_boot = False
    can_update = False
    keep_boot_order = False
    keep_mbr = False
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
    stage2_description = N_("/boot file system")
    stage2_max_end = Size("2 TiB")

    @property
    def stage2_format_types(self):
        # If the product file_system_type is valid, use it by default
        valid_fs = ["ext4", "ext3", "ext2"]
        if conf.storage.file_system_type in valid_fs:
            valid_fs.insert(0, conf.storage.file_system_type)

        return valid_fs

    # this is so stupid...
    global_preserve_args = ["speakup_synth", "apic", "noapic", "apm", "ide",
                            "noht", "acpi", "video", "pci", "nodmraid",
                            "nompath", "nomodeset", "noiswmd", "fips",
                            "selinux", "biosdevname", "ipv6.disable",
                            "net.ifnames"]
    preserve_args = []

    def __init__(self):
        super().__init__()
        self.boot_args = Arguments()
        self.dracut_args = Arguments()

        # the device the bootloader will be installed on
        self.stage1_device = None

        # the "boot disk", meaning the disk stage1 _will_ go on
        self.stage1_disk = None
        self.stage2_is_preferred_stage1 = False

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

        self.use_bls = True

        self.errors = []
        self.warnings = []

    def reset(self):
        """ Reset stage1 and stage2 values """
        self.stage1_device = None
        self.stage1_disk = None
        self.stage2_device = None
        self.stage2_is_preferred_stage1 = False
        self.disks = []

        self.errors = []
        self.warnings = []

    #
    # disk list access
    #
    @property
    def disk_order(self):
        """Potentially partial order for disks."""
        return self._disk_order

    @disk_order.setter
    def disk_order(self, order):
        log.debug("new disk order: %s", order)
        self._disk_order = order
        if self.disks:
            self._sort_disks()

    def _sort_disks(self):
        """Sort the internal disk list."""
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
        log.debug("new disk list: %s", self.disks)

    #
    # image list access
    #
    @property
    def default(self):
        """The default image."""
        if not self._default_image and self.linux_images:
            self._default_image = self.linux_images[0]

        return self._default_image

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
        return DiskLabel.get_platform_label_types()

    @property
    def device_descriptions(self):
        return platform.platform.boot_stage1_constraint_dict["descriptions"]

    #
    # constraint checking for target devices
    #
    def _is_valid_md(self, device, raid_levels=None,
                     metadata=None, member_types=None, desc=""):
        ret = True
        if device.type != "mdarray":
            return ret

        if raid_levels and device.level not in raid_levels:
            levels_str = ",".join("%s" % l for l in raid_levels)
            self.errors.append(_("RAID sets that contain '%(desc)s' must have one "
                                 "of the following raid levels: %(raid_level)s.")
                               % {"desc": desc, "raid_level": levels_str})
            ret = False

        # new arrays will be created with an appropriate metadata format
        if device.exists and \
           metadata and device.metadata_version not in metadata:
            self.errors.append(_("RAID sets that contain '%(desc)s' must have one "
                                 "of the following metadata versions: %(metadata_versions)s.")
                               % {"desc": desc, "metadata_versions": ",".join(metadata)})
            ret = False

        if member_types:
            for member in device.members:
                if not self._device_type_match(member, member_types):
                    self.errors.append(_("RAID sets that contain '%(desc)s' must "
                                         "have one of the following device "
                                         "types: %(types)s.")
                                       % {"desc": desc, "types": ",".join(member_types)})
                    ret = False

        log.debug("_is_valid_md(%s) returning %s", device.name, ret)
        return ret

    def _is_valid_disklabel(self, device, disklabel_types=None):
        ret = True
        if self.disklabel_types:
            for disk in device.disks:
                label_type = getattr(disk.format, "label_type", None)
                if not label_type or label_type not in self.disklabel_types:
                    types_str = ",".join(disklabel_types)
                    self.errors.append(_("%(name)s must have one of the following "
                                         "disklabel types: %(types)s.")
                                       % {"name": device.name, "types": types_str})
                    ret = False

        log.debug("_is_valid_disklabel(%s) returning %s", device.name, ret)
        return ret

    def _is_valid_format(self, device, format_types=None, mountpoints=None,
                         desc=""):
        ret = True
        if format_types and device.format.type not in format_types:
            self.errors.append(_("%(desc)s cannot be of type %(type)s.")
                               % {"desc": desc, "type": device.format.type})
            ret = False

        if mountpoints and hasattr(device.format, "mountpoint") \
           and device.format.mountpoint not in mountpoints:
            self.errors.append(_("%(desc)s must be mounted on one of %(mountpoints)s.")
                               % {"desc": desc, "mountpoints": ", ".join(mountpoints)})
            ret = False

        log.debug("_is_valid_format(%s) returning %s", device.name, ret)
        return ret

    def _is_valid_size(self, device, desc=""):
        ret = True
        msg = None
        errors = []
        if device.format.min_size and device.format.max_size:
            msg = (_("%(desc)s must be between %(min)d and %(max)d MB in size")
                   % {"desc": desc, "min": device.format.min_size,
                      "max": device.format.max_size})

        if device.format.min_size and device.size < device.format.min_size:
            if msg is None:
                errors.append(_("%(desc)s must not be smaller than %(min)dMB.")
                              % {"desc": desc, "min": device.format.min_size})
            else:
                errors.append(msg)

            ret = False

        if device.format.max_size and device.size > device.format.max_size:
            if msg is None:
                errors.append(_("%(desc)s must not be larger than %(max)dMB.")
                              % {"desc": desc, "max": device.format.max_size})
            elif msg not in errors:
                # don't add the same error string twice
                errors.append(msg)

            ret = False

        log.debug("_is_valid_size(%s) returning %s", device.name, ret)
        return ret

    def _is_valid_location(self, device, max_end=None, desc=""):
        ret = True
        if max_end and device.type == "partition" and device.parted_partition:
            end_sector = device.parted_partition.geometry.end
            sector_size = device.parted_partition.disk.device.sectorSize
            end = Size(sector_size * end_sector)
            if end > max_end:
                self.errors.append(_("%(desc)s must be within the first %(max_end)s of "
                                     "the disk.") % {"desc": desc, "max_end": max_end})
                ret = False

        log.debug("_is_valid_location(%s) returning %s", device.name, ret)
        return ret

    def _is_valid_partition(self, device, primary=None, desc=""):
        ret = True
        if device.type == "partition" and primary and not device.is_primary:
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
            if "disk" in types and device.is_disk:
                index = types.index("disk")

        return index

    def _device_type_match(self, device, types):
        """ Return True if device is of one of the types in the list types. """
        return self._device_type_index(device, types) is not None

    def device_description(self, device):
        device_types = list(self.device_descriptions.keys())
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
        constraint = platform.platform.boot_stage1_constraint_dict

        if device is None:
            return False

        if not self._device_type_match(device, constraint["device_types"]):
            log.debug("stage1 device cannot be of type %s", device.type)
            return False

        if _is_on_sw_iscsi(device):
            if not _is_on_ibft(device):
                if conf.bootloader.nonibft_iscsi_boot:
                    log.debug("stage1 device on non-iBFT iSCSI disk allowed "
                              "by boot option inst.iscsi.nonibftboot")
                else:
                    log.debug("stage1 device cannot be on an non-iBFT iSCSI disk")
                    self.errors.append(_("Boot loader stage1 device cannot be on "
                                         "an iSCSI disk which is not configured in iBFT."))
                    return False

        description = self.device_description(device)

        if self.stage2_is_valid_stage1 and device == self.stage2_device:
            # special case
            valid = (self.stage2_is_preferred_stage1 and
                     self.is_valid_stage2_device(device))

            # we'll be checking stage2 separately so don't duplicate messages
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
                                       max_end=constraint["max_end"],
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

        # Track the errors set by validity check in case no device would be found.
        errors = []
        for device in devices:
            if self.stage1_disk not in device.disks:
                continue

            if self.is_valid_stage1_device(device):
                if conf.target.is_image and device.is_disk:
                    # GRUB2 will install to /dev/loop0 but not to
                    # /dev/mapper/<image_name>
                    self.stage1_device = device.parents[0]
                else:
                    self.stage1_device = device

                break
            errors.extend(self.errors)

        if not self.stage1_device:
            self.reset()
            msg = "Failed to find a suitable stage1 device"
            if errors:
                msg = msg + ": " + "; ".join(errors)
            raise BootLoaderError(msg)

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

        if _is_on_sw_iscsi(device):
            if not _is_on_ibft(device):
                if conf.bootloader.nonibft_iscsi_boot:
                    log.info("%s on non-iBFT iSCSI disk allowed by boot option inst.nonibftiscsiboot",
                             self.stage2_description)
                else:
                    self.errors.append(_("%(bootloader_stage2_description)s cannot be on "
                                         "an iSCSI disk which is not configured in iBFT.")
                                       % {"bootloader_stage2_description":
                                          self.stage2_description})
                    valid = False

        if not self._device_type_match(device, self.stage2_device_types):
            self.errors.append(_("%(desc)s cannot be of type %(type)s")
                               % {"desc": _(self.stage2_description), "type": device.type})
            valid = False

        if not self._is_valid_disklabel(device,
                                        disklabel_types=self.disklabel_types):
            valid = False

        if not self._is_valid_size(device, desc=_(self.stage2_description)):
            valid = False

        if self.stage2_max_end and not self._is_valid_location(device,
                                                               max_end=self.stage2_max_end,
                                                               desc=_(self.stage2_description)):
            valid = False

        if not self._is_valid_partition(device,
                                        primary=self.stage2_must_be_primary):
            valid = False

        if not self._is_valid_md(device,
                                 raid_levels=self.stage2_raid_levels,
                                 metadata=self.stage2_raid_metadata,
                                 member_types=self.stage2_raid_member_types,
                                 desc=_(self.stage2_description)):
            valid = False

        if linux and \
           not self._is_valid_format(device,
                                     format_types=self.stage2_format_types,
                                     mountpoints=self.stage2_mountpoints,
                                     desc=_(self.stage2_description)):
            valid = False

        non_linux_format_types = platform.platform._non_linux_format_types
        if non_linux and \
           not self._is_valid_format(device,
                                     format_types=non_linux_format_types):
            valid = False

        if not self.encryption_support and device.encrypted:
            self.errors.append(_("%s cannot be on an encrypted block "
                                 "device.") % _(self.stage2_description))
            valid = False

        log.debug("is_valid_stage2_device(%s) returning %s", device.name, valid)
        return valid

    #
    # miscellaneous
    #

    def has_windows(self, devices):
        return False

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

    @timeout.setter
    def timeout(self, seconds):
        self._timeout = seconds

    @property
    def update_only(self):
        return self._update_only

    @update_only.setter
    def update_only(self, value):
        if value and not self.can_update:
            raise ValueError("this boot loader does not support updates")
        elif self.can_update:
            self._update_only = value

    def set_boot_args(self, storage):
        """Set up the boot command line."""
        self._set_storage_boot_args(storage)
        self._preserve_some_boot_args()
        self._set_graphical_boot_args()

    def _set_storage_boot_args(self, storage):
        """Set the storage boot args."""
        fcoe_proxy = STORAGE.get_proxy(FCOE)
        iscsi_proxy = STORAGE.get_proxy(ISCSI)

        # FIPS
        boot_device = storage.mountpoints.get("/boot")
        if flags.cmdline.get("fips") == "1" and boot_device:
            self.boot_args.add("boot=%s" % self.stage2_device.fstab_spec)

        # Storage
        dracut_devices = [storage.root_device]
        if self.stage2_device != storage.root_device:
            dracut_devices.append(self.stage2_device)

        swap_devices = storage.fsset.swap_devices
        dracut_devices.extend(swap_devices)

        # Add resume= option to enable hibernation on x86.
        # Choose the largest swap device for that.
        if blivet.arch.is_x86() and swap_devices:
            resume_device = max(swap_devices, key=lambda x: x.size)
            self.boot_args.add("resume=%s" % resume_device.fstab_spec)

        # Does /usr have its own device? If so, we need to tell dracut
        usr_device = storage.mountpoints.get("/usr")
        if usr_device:
            dracut_devices.extend([usr_device])

        netdevs = [d for d in storage.devices \
                   if (getattr(d, "complete", True) and
                       isinstance(d, NetworkStorageDevice))]

        rootdev = storage.root_device
        if any(rootdev.depends_on(netdev) for netdev in netdevs):
            dracut_devices = set(dracut_devices)
            # By this time this thread should be the only one running, and also
            # mountpoints is a property function that returns a new dict every
            # time, so iterating over the values is safe.
            for dev in storage.mountpoints.values():
                if any(dev.depends_on(netdev) for netdev in netdevs):
                    dracut_devices.add(dev)

        done = []
        for device in dracut_devices:
            for dep in storage.devices:
                if dep in done:
                    continue

                if device != dep and not device.depends_on(dep):
                    continue

                if isinstance(dep, blivet.devices.FcoeDiskDevice):
                    setup_args = fcoe_proxy.GetDracutArguments(dep.nic)
                elif isinstance(dep, blivet.devices.iScsiDiskDevice):
                    # (partial) offload devices do not need setup in dracut
                    if not dep.offload:
                        node = _get_iscsi_node_from_device(dep)
                        setup_args = iscsi_proxy.GetDracutArguments(Node.to_structure(node))
                else:
                    setup_args = dep.dracut_setup_args()

                if not setup_args:
                    continue

                self.boot_args.update(setup_args)
                self.dracut_args.update(setup_args)
                done.append(dep)

                # network configuration arguments
                if isinstance(dep, NetworkStorageDevice):
                    network_proxy = NETWORK.get_proxy()
                    network_args = []
                    if isinstance(dep, blivet.devices.iScsiDiskDevice):
                        if dep.iface == "default" or ":" in dep.iface:
                            node = _get_iscsi_node_from_device(dep)
                            if iscsi_proxy.IsNodeFromIbft(Node.to_structure(node)):
                                nic = ibft_iface()
                            else:
                                nic = iface_for_host_ip(dep.host_address)
                        else:
                            nic = iscsi_proxy.GetInterface(dep.iface)
                    else:
                        nic = dep.nic
                    if nic:
                        network_args = network_proxy.GetDracutArguments(nic, dep.host_address, "")

                    self.boot_args.update(network_args)
                    self.dracut_args.update(network_args)

        # This is needed for FCoE, bug #743784. The case:
        # We discover LUN on an iface which is part of multipath setup.
        # If the iface is disconnected after discovery anaconda doesn't
        # write dracut ifname argument for the disconnected iface path
        # (in NETWORK.GetDracutArguments).
        # Dracut needs the explicit ifname= because biosdevname
        # fails to rename the iface (because of BFS booting from it).
        for nic in fcoe_proxy.GetNics():
            hwaddr = get_interface_hw_address(nic)
            if hwaddr:
                self.boot_args.add("ifname=%s:%s" % (nic, hwaddr.lower()))

        # Add rd.iscsi.firmware to trigger dracut running iscsistart
        # See rhbz#1099603 and rhbz#1185792
        if len(glob("/sys/firmware/iscsi_boot*")) > 0:
            self.boot_args.add("rd.iscsi.firmware")

    def _preserve_some_boot_args(self):
        """Preserve some of the boot args."""
        for opt in self.global_preserve_args + self.preserve_args:
            if opt not in flags.cmdline:
                continue

            arg = flags.cmdline.get(opt)
            new_arg = opt
            if arg:
                new_arg += "=%s" % arg

            self.boot_args.add(new_arg)

    def _set_graphical_boot_args(self):
        """Set up the graphical boot."""
        args = []

        try:
            import rpm
        except ImportError:
            pass
        else:
            util.resetRpmDb()
            ts = rpm.TransactionSet(util.getSysroot())

            # Only add "rhgb quiet" on non-s390, non-serial installs.
            if util.isConsoleOnVirtualTerminal() \
                    and (ts.dbMatch('provides', 'rhgb').count()
                         or ts.dbMatch('provides', 'plymouth').count()):

                args = ["rhgb", "quiet"]

        self.boot_args.update(args)
        self.dracut_args.update(args)

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
        pass

    def write_config(self):
        """ Write the bootloader configuration. """
        if not self.config_file:
            raise BootLoaderError("no config file defined for this boot loader")

        config_path = os.path.normpath(util.getSysroot() + self.config_file)
        if os.access(config_path, os.R_OK):
            os.rename(config_path, config_path + ".anacbak")

        config = util.open_with_perm(config_path, "w", self.config_file_mode)
        self.write_config_header(config)
        self.write_config_images(config)
        config.close()
        self.write_config_post()

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
        os.sync()
        self.stage2_device.format.sync(root=util.getTargetPhysicalRoot())
        self.install()

    def install(self, args=None):
        raise NotImplementedError()

    def update(self):
        """ Update an existing bootloader configuration. """
        pass


def get_interface_hw_address(iface):
    """Get hardware address of network interface."""
    network_proxy = NETWORK.get_proxy()
    device_infos = NetworkDeviceInfo.from_structure_list(network_proxy.GetSupportedDevices())

    for info in device_infos:
        if info.device_name == iface:
            return info.hw_address
    return ""
