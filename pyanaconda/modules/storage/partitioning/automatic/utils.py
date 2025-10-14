#
# Copyright (C) 2009-2015  Red Hat, Inc.
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
# Red Hat Author(s): Dave Lehman <dlehman@redhat.com>
#
import parted
from blivet.devices.luks import LUKSDevice
from blivet.devices.lvm import DEFAULT_THPOOL_RESERVE
from blivet.devices.partition import FALLBACK_DEFAULT_PART_SIZE, PartitionDevice
from blivet.errors import NoDisksError, NotEnoughFreeSpaceError
from blivet.formats import get_format
from blivet.formats.luks import LUKS2PBKDFArgs
from blivet.partitioning import get_free_regions, get_next_partition_type
from blivet.size import Size
from pykickstart.constants import (
    AUTOPART_TYPE_BTRFS,
    AUTOPART_TYPE_LVM,
    AUTOPART_TYPE_LVM_THINP,
    AUTOPART_TYPE_PLAIN,
)

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.i18n import _
from pyanaconda.modules.common.errors.storage import ProtectedDeviceError
from pyanaconda.modules.storage.partitioning.specification import PartSpec
from pyanaconda.modules.storage.platform import platform

log = get_module_logger(__name__)


def get_pbkdf_args(luks_version, pbkdf_type=None, max_memory_kb=0, iterations=0, time_ms=0):
    """Get the pbkdf arguments.

    :param luks_version: a version of LUKS
    :param pbkdf_type: a type of PBKDF
    :param max_memory_kb: a memory cost for PBKDF
    :param iterations: a number of iterations
    :param time_ms: an iteration time in ms
    :return:
    """
    # PBKDF arguments are not supported for LUKS 1.
    if luks_version != "luks2":
        return None

    # Use defaults.
    if not pbkdf_type and not max_memory_kb and not iterations and not time_ms:
        log.debug("Using default PBKDF args.")
        return None

    # Use specified arguments.
    return LUKS2PBKDFArgs(pbkdf_type or None, max_memory_kb or 0, iterations or 0, time_ms or 0)


def lookup_alias(devicetree, alias):
    """Look up a device of the given alias in the device tree.

    :param devicetree: a device tree to look up devices
    :param alias: an alias name
    :return: a device object
    """
    for dev in devicetree.devices:
        if getattr(dev, "req_name", None) == alias:
            return dev

    return None


def shrink_device(storage, device, size):
    """Shrink the size of the device.

    :param storage: a storage model
    :param device: a device to shrink
    :param size: a new size of the device
    """
    if device.protected:
        raise ProtectedDeviceError(device.name)

    # The device size is small enough.
    if device.size <= size:
        log.debug("The size of %s is already %s.", device.name, device.size)
        return

    # Resize the device.
    log.debug("Shrinking a size of %s to %s.", device.name, size)
    aligned_size = device.align_target_size(size)
    storage.resize_device(device, aligned_size)


def remove_device(storage, device):
    """Remove a device after removing its dependent devices.

    If the device is protected, do nothing. If the device has
    protected children, just remove the unprotected ones.

    :param storage: a storage model
    :param device: a device to remove
    """
    if device.protected:
        raise ProtectedDeviceError(device.name)

    # Only remove unprotected children if any protected.
    if any(d.protected for d in device.children):
        log.debug("Removing unprotected children of %s.", device.name)

        for child in (d for d in device.children if not d.protected):
            storage.recursive_remove(child)

        return

    # No protected children, remove the device
    log.debug("Removing device %s.", device.name)
    storage.recursive_remove(device)


def get_candidate_disks(storage):
    """Return a list of disks to be used for autopart/reqpart.

    Disks must be partitioned and have a single free region large enough
    for a default-sized (500MiB) partition.

    :param storage: the storage object
    :type storage: an instance of InstallerStorage
    :return: a list of partitioned disks with at least 500MiB of free space
    :rtype: list of :class:`blivet.devices.StorageDevice`
    """
    usable_disks = []
    for disk in storage.partitioned:
        if not disk.format.supported or disk.protected:
            continue
        usable_disks.append(disk)

    free_disks = []
    for disk in usable_disks:
        if get_next_partition_type(disk.format.parted_disk) is None:
            # new partition can't be added to the disk -- there is no free slot
            # for a primary partition and no extended partition
            continue

        part = disk.format.first_partition
        while part:
            if not part.type & parted.PARTITION_FREESPACE:
                part = part.nextPartition()
                continue

            if Size(part.getLength(unit="B")) > PartitionDevice.default_size:
                free_disks.append(disk)
                break

            part = part.nextPartition()

    if not usable_disks:
        raise NoDisksError(_("No usable disks selected."))

    if not free_disks:
        raise NotEnoughFreeSpaceError(_("Not enough free space on selected disks."))

    return free_disks


def get_disks_for_implicit_partitions(disks, scheme, requests):
    """Return a list of disks that can be used for implicit partitions.

    :param disks: a list of candidate disks
    :param scheme: a type of the partitioning scheme
    :param requests: a list of partitioning requests
    :return: a list of disks that can be used for implicit partitions
    """
    # There will be no implicit partitions.
    if scheme == AUTOPART_TYPE_PLAIN:
        return []

    # Calculate slots for requested partitions.
    requested_slots = 0

    for request in requests:
        if request.is_partition(scheme):
            requested_slots += 1

    # Collect extra disks for implicit partitions.
    extra_disks = []

    for disk in disks:
        parted_disk = disk.format.parted_disk
        supports_extended = parted_disk.supportsFeature(parted.DISK_TYPE_EXTENDED)
        available_slots = parted_disk.maxPrimaryPartitionCount - parted_disk.primaryPartitionCount

        # Skip disks that will be used for requested partitions.
        if requested_slots and not supports_extended and available_slots <= requested_slots:
            requested_slots -= available_slots
            log.debug("Don't use %s for implicit partitions.", disk.name)
        else:
            requested_slots = 0
            extra_disks.append(disk)

    log.debug("Found disks for implicit partitions: %s", [d.name for d in extra_disks])
    return extra_disks


def schedule_implicit_partitions(storage, disks, scheme, encrypted=False, luks_fmt_args=None):
    """Schedule creation of a lvm/btrfs member partitions for autopart.

    We create one such partition on each disk. They are not allocated until
    later (in :func:`doPartitioning`).

    :param storage: the storage object
    :type storage: an instance of InstallerStorage
    :param disks: list of partitioned disks with free space
    :type disks: list of :class:`blivet.devices.StorageDevice`
    :param scheme: a type of the partitioning scheme
    :type scheme: int
    :param encrypted: encrypt the scheduled partitions
    :type encrypted: bool
    :param luks_fmt_args: arguments for the LUKS format constructor
    :type luks_fmt_args: dict
    :return: list of newly created (unallocated) partitions
    :rtype: list of :class:`blivet.devices.PartitionDevice`
    """
    # create a separate pv or btrfs partition for each disk with free space
    devs = []

    # only schedule the partitions if either lvm or btrfs autopart was chosen
    if scheme == AUTOPART_TYPE_PLAIN:
        return devs

    for disk in disks:
        if encrypted:
            fmt_type = "luks"
            fmt_args = luks_fmt_args or {}
        else:
            if scheme in (AUTOPART_TYPE_LVM, AUTOPART_TYPE_LVM_THINP):
                fmt_type = "lvmpv"
            else:
                fmt_type = "btrfs"
            fmt_args = {}
        part = storage.new_partition(fmt_type=fmt_type,
                                     fmt_args=fmt_args,
                                     grow=True,
                                     parents=[disk])
        storage.create_device(part)
        devs.append(part)
        log.debug("Created the implicit partition %s for %s.", part.name, disk.name)

    return devs


def get_default_partitioning():
    """Get the default partitioning requests.

    :return: a list of partitioning specs
    """
    # Get the platform-specific partitioning.
    partitioning = list(platform.partitions)

    # Get the product-specific partitioning.
    for attrs in conf.storage.default_partitioning:
        partitioning.append(get_part_spec(attrs))

    return partitioning


def get_part_spec(attrs):
    """Creates an instance of PartSpec.

    :param attrs: A dictionary containing the configuration
    :return: a partitioning spec
    :rtype: PartSpec
    """
    name = attrs.get("name")
    swap = name == "swap"
    schemes = set()

    if attrs.get("btrfs"):
        schemes.add(AUTOPART_TYPE_BTRFS)

    spec = PartSpec(
        mountpoint=name if not swap else None,
        fstype=None if not swap else "swap",
        lv=True,
        thin=not swap,
        btr=not swap,
        size=attrs.get("min") or attrs.get("size"),
        max_size=attrs.get("max"),
        grow="min" in attrs,
        required_space=attrs.get("free") or 0,
        encrypted=True,
        schemes=schemes,
    )
    return spec

def schedule_partitions(storage, disks, implicit_devices, scheme, requests, encrypted=False,
                        luks_fmt_args=None):
    """Schedule creation of autopart/reqpart partitions.

    This only schedules the requests for actual partitions.

    :param storage: the storage object
    :type storage: an instance of InstallerStorage
    :param disks: list of partitioned disks with free space
    :type disks: list of :class:`blivet.devices.StorageDevice`
    :param implicit_devices: list of implicit devices
    :type implicit_devices: list of :class:`blivet.devices.StorageDevice`
    :param scheme: a type of the partitioning scheme
    :type scheme: int
    :param requests: list of partitioning requests
    :type requests: list of :class:`~.storage.partspec.PartSpec` instances
    :param encrypted: encrypt the scheduled partitions
    :type encrypted: bool
    :param luks_fmt_args: arguments for the LUKS format constructor
    :type luks_fmt_args: dict
    """
    # basis for requests with required_space is the sum of the sizes of the
    # two largest free regions
    all_free = (Size(reg.getLength(unit="B")) for reg in get_free_regions(disks))
    all_free = sorted(all_free, reverse=True)
    if not all_free:
        # this should never happen since we've already filtered the disks
        # to those with at least 500MiB free
        log.error("no free space on disks %s", [d.name for d in disks])
        return

    free = all_free[0]
    if len(all_free) > 1:
        free += all_free[1]

    # The boot disk must be set at this point. See if any platform-specific
    # stage1 device we might allocate already exists on the boot disk.
    stage1_device = None
    for device in storage.devices:
        if storage.bootloader.stage1_disk not in device.disks:
            continue

        if storage.bootloader.is_valid_stage1_device(device, early=True):
            stage1_device = device
            break

    #
    # First pass is for partitions only. We'll do LVs later.
    #
    for request in requests:
        use_disks = disks[:]
        if request.lv and scheme in (AUTOPART_TYPE_LVM, AUTOPART_TYPE_LVM_THINP):
            continue

        if request.btr and scheme == AUTOPART_TYPE_BTRFS:
            continue

        if request.required_space and request.required_space > free:
            continue

        elif request.fstype in ("prepboot", "efi", "macefi", "hfs+") and \
                (storage.bootloader.skip_bootloader or stage1_device):
            # there should never be a need for more than one of these
            # partitions, so skip them.
            log.info("skipping unneeded stage1 %s request", request.fstype)
            log.debug("%s", request)

            if request.fstype in ["efi", "macefi"] and stage1_device:
                # Set the mountpoint for the existing EFI boot partition
                stage1_device.format.mountpoint = "/boot/efi"

            log.debug("%s", stage1_device)
            continue
        elif request.fstype == "biosboot":
            is_gpt = (stage1_device and
                      getattr(stage1_device.format, "label_type", None) == "gpt")
            has_bios_boot = (stage1_device and
                             any(p.format.type == 'biosboot'
                                 for p in storage.partitions
                                 if p.disk == stage1_device))
            if (storage.bootloader.skip_bootloader or
                not (stage1_device and stage1_device.is_disk and
                     is_gpt and not has_bios_boot)):
                # there should never be a need for more than one of these
                # partitions, so skip them.
                log.info("skipping unneeded stage1 %s request", request.fstype)
                log.debug("%s", request)
                log.debug("%s", stage1_device)
                continue

            log.debug("making sure biosboot is placed on %s", stage1_device.name)
            use_disks = [stage1_device]

        if request.size > all_free[0]:
            # no big enough free space for the requested partition
            mountpoint_info = f" {request.mountpoint}" if request.mountpoint else ""
            fstype_info = f" ({request.fstype})" if request.fstype else ""
            raise NotEnoughFreeSpaceError(_("No suitable free space found for automatic "
                                            "partitioning for{mountpoint}{fstype}: "
                                            "requested {size}, largest free space {free}").format(
                                                mountpoint=mountpoint_info,
                                                fstype=fstype_info,
                                                size=request.size,
                                                free=all_free[0]))

        if request.encrypted and encrypted:
            fmt_type = "luks"
            fmt_args = luks_fmt_args or {}
        else:
            fmt_type = request.fstype
            fmt_args = {}

        dev = storage.new_partition(fmt_type=fmt_type,
                                    fmt_args=fmt_args,
                                    size=request.size,
                                    grow=request.grow,
                                    maxsize=request.max_size,
                                    mountpoint=request.mountpoint,
                                    parents=use_disks)

        # schedule the device for creation
        storage.create_device(dev)

        if request.encrypted and encrypted:
            luks_fmt = get_format(request.fstype,
                                  device=dev.path,
                                  mountpoint=request.mountpoint)
            luks_dev = LUKSDevice("luks-%s" % dev.name,
                                  fmt=luks_fmt,
                                  size=dev.size,
                                  parents=dev)
            storage.create_device(luks_dev)

        if scheme in (AUTOPART_TYPE_LVM, AUTOPART_TYPE_LVM_THINP, AUTOPART_TYPE_BTRFS) and \
                implicit_devices:
            # doing LVM/BTRFS -- make sure the newly created partition fits in some
            # free space together with one of the implicitly requested partitions
            smallest_implicit = sorted(implicit_devices, key=lambda d: d.size)[0]
            if (request.size + smallest_implicit.size) > all_free[0]:
                # not enough space to allocate the smallest implicit partition
                # and the request, make the implicit partitions smaller in
                # attempt to make space for the request
                for implicit_req in implicit_devices:
                    implicit_req.size = FALLBACK_DEFAULT_PART_SIZE

    return implicit_devices


def schedule_volumes(storage, devices, scheme, requests, encrypted=False):
    """Schedule creation of autopart lvm/btrfs volumes.

    Schedules encryption of member devices if requested, schedules creation
    of the container (:class:`blivet.devices.LVMVolumeGroupDevice` or
    :class:`blivet.devices.BTRFSVolumeDevice`) then schedules creation of the
    autopart volume requests.

    If an appropriate bootloader stage1 device exists on the boot drive, any
    autopart request to create another one will be skipped/discarded.

    :param storage: the storage object
    :type storage: an instance of InstallerStorage
    :param devices: list of member partitions
    :type devices: list of :class:`blivet.devices.PartitionDevice`
    :param scheme: a type of the partitioning scheme
    :type scheme: int
    :param requests: list of partitioning requests
    :type requests: list of :class:`~.storage.partspec.PartSpec` instances
    :param encrypted: encrypt the scheduled partitions
    :type encrypted: bool
    """
    if not devices:
        return

    if scheme in (AUTOPART_TYPE_LVM, AUTOPART_TYPE_LVM_THINP):
        new_container = storage.new_vg
        new_volume = storage.new_lv
        format_name = "lvmpv"
    else:
        new_container = storage.new_btrfs
        new_volume = storage.new_btrfs
        format_name = "btrfs"

    if encrypted:
        pvs = []
        for dev in devices:
            pv = LUKSDevice("luks-%s" % dev.name,
                            fmt=get_format(format_name, device=dev.path),
                            size=dev.size,
                            parents=dev)
            pvs.append(pv)
            storage.create_device(pv)
    else:
        pvs = devices

    # create a vg containing all of the autopart pvs
    container = new_container(parents=pvs)
    storage.create_device(container)

    #
    # Convert requests into Device instances and schedule them for creation.
    #
    # Second pass, for LVs only.
    pool = None
    for request in requests:
        btr = bool(scheme == AUTOPART_TYPE_BTRFS and request.btr)
        lv = bool(scheme in (AUTOPART_TYPE_LVM, AUTOPART_TYPE_LVM_THINP) and request.lv)
        thinlv = bool(scheme == AUTOPART_TYPE_LVM_THINP and request.lv and request.thin)

        if thinlv and pool is None:
            # create a single thin pool in the vg
            pool = storage.new_lv(parents=[container], thin_pool=True, grow=True)
            storage.create_device(pool)

            # make sure VG reserves space for the pool to grow if needed
            container.thpool_reserve = DEFAULT_THPOOL_RESERVE

        if not btr and not lv and not thinlv:
            continue

        # required space isn't relevant on btrfs
        if (lv or thinlv) and \
           request.required_space and request.required_space > container.size:
            continue

        if request.fstype is None:
            if btr:
                # btrfs volumes can only contain btrfs filesystems
                request.fstype = "btrfs"
            else:
                request.fstype = storage.default_fstype

        kwargs = {"mountpoint": request.mountpoint,
                  "fmt_type": request.fstype}
        if lv or thinlv:
            if thinlv:
                parents = [pool]
            else:
                parents = [container]

            kwargs.update({"parents": parents,
                           "grow": request.grow,
                           "maxsize": request.max_size,
                           "size": request.size,
                           "thin_volume": thinlv})
        else:
            kwargs.update({"parents": [container],
                           "size": request.size,
                           "subvol": True})

        dev = new_volume(**kwargs)

        # schedule the device for creation
        storage.create_device(dev)
