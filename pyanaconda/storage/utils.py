#
# Copyright (C) 2014  Red Hat, Inc.
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

"""UI-independent storage utility functions"""
import re
import locale
import os
import time
import requests

from decimal import Decimal

from blivet import udev
from blivet.size import Size
from blivet.errors import StorageError
from blivet.formats import device_formats
from blivet.formats.fs import FS
from blivet.formats.luks import LUKS2PBKDFArgs
from blivet.devicefactory import DEVICE_TYPE_LVM
from blivet.devicefactory import DEVICE_TYPE_LVM_THINP
from blivet.devicefactory import DEVICE_TYPE_BTRFS
from blivet.devicefactory import DEVICE_TYPE_MD
from blivet.devicefactory import DEVICE_TYPE_PARTITION
from blivet.devicefactory import DEVICE_TYPE_DISK
from blivet.devicefactory import is_supported_device_type
from blivet.util import total_memory
from bytesize.bytesize import ROUND_HALF_UP

from pykickstart.errors import KickstartError

from pyanaconda.core import util
from pyanaconda.core.i18n import N_, _, P_
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.modules.common.constants.services import NETWORK, STORAGE
from pyanaconda.modules.common.constants.objects import DISK_SELECTION, NVDIMM

from pykickstart.constants import AUTOPART_TYPE_PLAIN, AUTOPART_TYPE_BTRFS
from pykickstart.constants import AUTOPART_TYPE_LVM, AUTOPART_TYPE_LVM_THINP

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

# TODO: all those constants and mappings should go to blivet
# Used for info about device with no more supported type (ie btrfs).
DEVICE_TYPE_UNSUPPORTED = -1

DEVICE_TEXT_MAP = {
    DEVICE_TYPE_UNSUPPORTED: N_("Unsupported"),
    DEVICE_TYPE_LVM: N_("LVM"),
    DEVICE_TYPE_MD: N_("RAID"),
    DEVICE_TYPE_PARTITION: N_("Standard Partition"),
    DEVICE_TYPE_BTRFS: N_("Btrfs"),
    DEVICE_TYPE_LVM_THINP: N_("LVM Thin Provisioning"),
    DEVICE_TYPE_DISK: N_("Disk")
}

PARTITION_ONLY_FORMAT_TYPES = ("macefi", "prepboot", "biosboot", "appleboot")

MOUNTPOINT_DESCRIPTIONS = {"Swap": N_("The 'swap' area on your computer is used by the operating\n"
                                      "system when running low on memory."),
                           "Boot": N_("The 'boot' area on your computer is where files needed\n"
                                      "to start the operating system are stored."),
                           "Root": N_("The 'root' area on your computer is where core system\n"
                                      "files and applications are stored."),
                           "Home": N_("The 'home' area on your computer is where all your personal\n"
                                      "data is stored."),
                           "BIOS Boot": N_("The BIOS boot partition is required to enable booting\n"
                                           "from GPT-partitioned disks on BIOS hardware."),
                           "PReP Boot": N_("The PReP boot partition is required as part of the\n"
                                           "boot loader configuration on some PPC platforms.")}

AUTOPART_CHOICES = ((N_("Standard Partition"), AUTOPART_TYPE_PLAIN),
                    (N_("Btrfs"), AUTOPART_TYPE_BTRFS),
                    (N_("LVM"), AUTOPART_TYPE_LVM),
                    (N_("LVM Thin Provisioning"), AUTOPART_TYPE_LVM_THINP))

AUTOPART_DEVICE_TYPES = {AUTOPART_TYPE_LVM: DEVICE_TYPE_LVM,
                         AUTOPART_TYPE_LVM_THINP: DEVICE_TYPE_LVM_THINP,
                         AUTOPART_TYPE_PLAIN: DEVICE_TYPE_PARTITION,
                         AUTOPART_TYPE_BTRFS: DEVICE_TYPE_BTRFS}

NAMED_DEVICE_TYPES = (DEVICE_TYPE_BTRFS, DEVICE_TYPE_LVM, DEVICE_TYPE_MD, DEVICE_TYPE_LVM_THINP)
CONTAINER_DEVICE_TYPES = (DEVICE_TYPE_LVM, DEVICE_TYPE_BTRFS, DEVICE_TYPE_LVM_THINP)
SUPPORTED_DEVICE_TYPES = (DEVICE_TYPE_PARTITION, DEVICE_TYPE_LVM, DEVICE_TYPE_LVM_THINP)

# maximum ratio of swap size to disk size (10 %)
MAX_SWAP_DISK_RATIO = Decimal('0.1')

udev_device_dict_cache = None


def size_from_input(input_str, units=None):
    """ Get a Size object from an input string.

        :param str input_str: a string forming some representation of a size
        :param units: use these units if none specified in input_str
        :type units: str or NoneType
        :returns: a Size object corresponding to input_str
        :rtype: :class:`blivet.size.Size` or NoneType

        Units default to bytes if no units in input_str or units.
    """

    if not input_str:
        # Nothing to parse
        return None

    # A string ending with a digit contains no units information.
    if re.search(r'[\d.%s]$' % locale.nl_langinfo(locale.RADIXCHAR), input_str):
        input_str += units or ""

    try:
        size = Size(input_str)
    except ValueError:
        return None

    return size


def device_type_from_autopart(autopart_type):
    """Get device type matching the given autopart type."""

    return AUTOPART_DEVICE_TYPES.get(autopart_type, DEVICE_TYPE_LVM)


def bound_size(size, device, old_size):
    """ Returns a size bounded by the maximum and minimum size for
        the device.

        :param size: the candidate size
        :type size: :class:`blivet.size.Size`
        :param device: the device being displayed
        :type device: :class:`blivet.devices.StorageDevice`
        :param old_size: the fallback size
        :type old_size: :class:`blivet.size.Size`
        :returns: a size to which to set the device
        :rtype: :class:`blivet.size.Size`

        If size is 0, interpreted as set size to maximum possible.
        If no maximum size is available, reset size to old_size, but
        log a warning.
    """
    max_size = device.max_size
    min_size = device.min_size
    if not size:
        if max_size:
            log.info("No size specified, using maximum size for this device (%d).", max_size)
            size = max_size
        else:
            log.warning("No size specified and no maximum size available, setting size back to original size (%d).", old_size)
            size = old_size
    else:
        if max_size:
            if size > max_size:
                log.warning("Size specified (%d) is greater than the maximum size for this device (%d), using maximum size.", size, max_size)
                size = max_size
        else:
            log.warning("Unknown upper bound on size. Using requested size (%d).", size)

        if size < min_size:
            log.warning("Size specified (%d) is less than the minimum size for this device (%d), using minimum size.", size, min_size)
            size = min_size

    return size


def filter_unsupported_disklabel_devices(devices):
    """ Return input list minus any devices that exist on an unsupported disklabel. """
    return [d for d in devices
            if not any(not getattr(p, "disklabel_supported", True) for p in d.ancestors)]


def device_name_is_disk(device_name, devicetree=None, refresh_udev_cache=False):
    """Report if the given device name corresponds to a disk device.

    Check if the device name is a disk device or not. This function uses
    the provided Blivet devicetree for the checking and Blivet udev module
    if no devicetree is provided.

    Please note that the udev based check uses an internal cache that is generated
    when this function is first called in the udev checking mode. This basically
    means that udev devices added later will not be taken into account.
    If this is a problem for your usecase then use the refresh_udev_cache option
    to force a refresh of the udev cache.

    :param str device_name: name of the device to check
    :param devicetree: device tree to look up devices in (optional)
    :type devicetree: :class:`blivet.DeviceTree`
    :param bool refresh_udev_cache: governs if the udev device cache should be refreshed
    :returns: True if the device name corresponds to a disk, False if not
    :rtype: bool
    """
    if devicetree is None:
        global udev_device_dict_cache
        if device_name:
            if udev_device_dict_cache is None or refresh_udev_cache:
                # Lazy load the udev dick that contains the {device_name : udev_device,..,}
                # mappings. The operation could be quite costly due to udev_settle() calls,
                # so we cache it in this non-elegant way.
                # An unfortunate side effect of this is that udev devices that show up after
                # this function is called for the first time will not be taken into account.
                udev_device_dict_cache = dict()

                for d in udev.get_devices():
                    # Add the device name to the cache.
                    udev_device_dict_cache[udev.device_get_name(d)] = d
                    # If the device is md, add the md name as well.
                    if udev.device_is_md(d) and udev.device_get_md_name(d):
                        udev_device_dict_cache[udev.device_get_md_name(d)] = d

            udev_device = udev_device_dict_cache.get(device_name)
            return udev_device and udev.device_is_disk(udev_device)
        else:
            return False
    else:
        device = devicetree.get_device_by_name(device_name)
        return device and device.is_disk


def device_matches(spec, devicetree=None, disks_only=False):
    """Return names of block devices matching the provided specification.

    :param str spec: a device identifier (name, UUID=<uuid>, &c)
    :keyword devicetree: device tree to look up devices in (optional)
    :type devicetree: :class:`blivet.DeviceTree`
    :param bool disks_only: if only disk devices matching the spec should be returned
    :returns: names of matching devices
    :rtype: list of str

    The spec can contain multiple "sub specs" delimited by a |, for example:

    "sd*|hd*|vd*"

    In such case we resolve the specs from left to right and return all
    unique matches, for example:

    ["sda", "sda1", "sda2", "sdb", "sdb1", "vdb"]

    If disks_only is specified we only return
    disk devices matching the spec. For the example above
    the output with disks_only=True would be:

    ["sda", "sdb", "vdb"]

    Also note that parse methods will not have access to a devicetree, while execute
    methods will. The devicetree is superior in that it can resolve md
    array names and in that it reflects scheduled device removals, but for
    normal local disks udev.resolve_devspec should suffice.
    """

    matches = []
    # the device specifications might contain multiple "sub specs" separated by a |
    # - the specs are processed from left to right
    for single_spec in spec.split("|"):
        full_spec = single_spec
        if not full_spec.startswith("/dev/"):
            full_spec = os.path.normpath("/dev/" + full_spec)

        # the regular case
        single_spec_matches = udev.resolve_glob(full_spec)
        for match in single_spec_matches:
            if match not in matches:
                # skip non-disk devices in disk-only mode
                if disks_only and not device_name_is_disk(match):
                    continue
                matches.append(match)

        dev_name = None
        # Use spec here instead of full_spec to preserve the spec and let the
        # called code decide whether to treat the spec as a path instead of a name.
        if devicetree is None:
            # we run the spec through resolve_devspec() here as unlike resolve_glob()
            # it can also resolve labels and UUIDs
            dev_name = udev.resolve_devspec(single_spec)
            if disks_only and dev_name:
                if not device_name_is_disk(dev_name):
                    dev_name = None  # not a disk
        else:
            # devicetree can also handle labels and UUIDs
            device = devicetree.resolve_device(single_spec)
            if device:
                dev_name = device.name
                if disks_only and not device_name_is_disk(dev_name, devicetree=devicetree):
                    dev_name = None  # not a disk

        # The dev_name variable can be None if the spec is not not found or is not valid,
        # but we don't want that ending up in the list.
        if dev_name and dev_name not in matches:
            matches.append(dev_name)

    log.debug("%s matches %s for devicetree=%s and disks_only=%s",
              spec, matches, devicetree, disks_only)

    return matches


def get_supported_filesystems():
    fs_types = []
    for cls in device_formats.values():
        obj = cls()

        # btrfs is always handled by on_device_type_changed
        supported_fs = (obj.supported and obj.formattable and
                        (isinstance(obj, FS) or
                         obj.type in ["biosboot", "prepboot", "swap"]))
        if supported_fs:
            fs_types.append(obj)

    return fs_types


def get_supported_autopart_choices():
    return [c for c in AUTOPART_CHOICES if is_supported_device_type(AUTOPART_DEVICE_TYPES[c[1]])]


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


def ignore_nvdimm_blockdevs():
    """Add nvdimm devices to be ignored to the ignored disks."""
    if conf.target.is_directory:
        return

    nvdimm_proxy = STORAGE.get_proxy(NVDIMM)
    ignored_nvdimm_devs = nvdimm_proxy.GetDevicesToIgnore()

    if not ignored_nvdimm_devs:
        return

    log.debug("Adding NVDIMM devices %s to ignored disks", ",".join(ignored_nvdimm_devs))

    disk_select_proxy = STORAGE.get_proxy(DISK_SELECTION)
    ignored_disks = disk_select_proxy.IgnoredDisks
    ignored_disks.extend(ignored_nvdimm_devs)
    disk_select_proxy.SetIgnoredDisks(ignored_disks)


def ignore_oemdrv_disks():
    """Ignore disks labeled OEMDRV."""
    matched = device_matches("LABEL=OEMDRV", disks_only=True)

    for oemdrv_disk in matched:
        disk_select_proxy = STORAGE.get_proxy(DISK_SELECTION)
        ignored_disks = disk_select_proxy.IgnoredDisks

        if oemdrv_disk not in ignored_disks:
            log.info("Adding disk %s labeled OEMDRV to ignored disks.", oemdrv_disk)
            ignored_disks.append(oemdrv_disk)
            disk_select_proxy.SetIgnoredDisks(ignored_disks)


def download_escrow_certificate(url):
    """Download the escrow certificate.

    :param url: an URL of the certificate
    :return: a content of the certificate
    """
    # Do we need a network connection?
    if not url.startswith("/") and not url.startswith("file:"):
        network_proxy = NETWORK.get_proxy()

        if not network_proxy.Connected:
            raise KickstartError(_("Escrow certificate %s requires the network.") % url)

    # Download the certificate.
    log.info("Downloading an escrow certificate from: %s", url)

    try:
        request = util.requests_session().get(url, verify=True)
    except requests.exceptions.SSLError as e:
        raise KickstartError(_("SSL error while downloading the escrow certificate:\n\n%s") % e)
    except requests.exceptions.RequestException as e:
        raise KickstartError(_("The following error was encountered while downloading the "
                               "escrow certificate:\n\n%s") % e)

    try:
        certificate = request.content
    finally:
        request.close()

    return certificate


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


def find_live_backing_device(devicetree):
    """Find the backing device for the live image.

    Note that this is a little bit of a hack since we're assuming
    that /run/initramfs/live will exist

    :param devicetree: a device tree
    :return: a device or None
    """
    for mnt in open("/proc/mounts").readlines():
        if " /run/initramfs/live " not in mnt:
            continue

        # Return the device mounted at /run/initramfs/live.
        device_path = mnt.split()[0]
        device_name = device_path.split("/")[-1]
        device = devicetree.get_device_by_name(device_name, hidden=True)

        if device:
            return device

        # Or return the disk of this device.
        info = udev.get_device(device_node=device_path)
        disk_name = udev.device_get_partition_disk(info) if info else ""
        disk = devicetree.get_device_by_name(disk_name, hidden=True)

        if disk:
            return disk

    return None


def filter_disks_by_names(disks, names):
    """Filter disks by the given names.

    :param disks: a list of disks
    :param names: a list of disk names
    :return: a list of filtered disk names
    """
    return list(filter(lambda name: name in disks, names))


def check_disk_selection(storage, selected_disks):
    """Return a list of errors related to a proposed disk selection.

    :param storage: blivet.Blivet instance
    :param selected_disks: names of selected disks
    :type selected_disks: list of str
    :returns: a list of error messages
    :rtype: list of str
    """
    errors = []

    for name in selected_disks:
        selected = storage.devicetree.get_device_by_name(name, hidden=True)
        related = sorted(storage.devicetree.get_related_disks(selected), key=lambda d: d.name)
        missing = [r.name for r in related if r.name not in selected_disks]

        if not missing:
            continue

        errors.append(P_(
            "You selected disk %(selected)s, which contains "
            "devices that also use unselected disk "
            "%(unselected)s. You must select or de-select "
            "these disks as a set.",
            "You selected disk %(selected)s, which contains "
            "devices that also use unselected disks "
            "%(unselected)s. You must select or de-select "
            "these disks as a set.",
            len(missing)) % {
            "selected": selected.name,
            "unselected": ", ".join(missing)
        })

    return errors


def get_required_device_size(required_space, format_class=None):
    """Get the required device size for the given space.

    We need to provide information how big device is required to
    have successful installation. The argument ``format_class``
    should be filesystem format class for the **root** filesystem
    this class carry information about metadata size.

    :param required_space: the required space
    :param format_class: the class of the filesystem format.
    :returns: Size of the device with given filesystem format.
    """
    if not format_class:
        format_class = FS.biggest_overhead_FS()

    device_size = format_class.get_required_size(required_space)
    return device_size.round_to_nearest(Size("1 MiB"), ROUND_HALF_UP)


def suggest_swap_size(quiet=False, hibernation=False, disk_space=None):
    """Suggest the size of the swap partition that will be created.

    :param bool quiet: whether to log size information or not
    :param bool hibernation: calculate swap size big enough for hibernation
    :param disk_space: how much disk space is available
    :return: calculated swap size
    """
    mem = total_memory()
    mem = ((mem / 16) + 1) * 16

    if not quiet:
        log.info("Detected %s of memory", mem)

    sixty_four_gib = Size("64 GiB")

    # the succeeding if-statement implements the following formula for
    # suggested swap size.
    #
    # swap(mem) = 2 * mem, if mem < 2 GiB
    #           = mem,     if 2 GiB <= mem < 8 GiB
    #           = mem / 2, if 8 GIB <= mem < 64 GiB
    #           = 4 GiB,   if mem >= 64 GiB
    if mem < Size("2 GiB"):
        swap = 2 * mem

    elif mem < Size("8 GiB"):
        swap = mem

    elif mem < sixty_four_gib:
        swap = mem / 2

    else:
        swap = Size("4 GiB")

    if hibernation:
        if mem <= sixty_four_gib:
            swap = mem + swap
        else:
            log.info("Ignoring --hibernation option on systems with %s of RAM or more",
                     sixty_four_gib)

    if disk_space is not None and not hibernation:
        max_swap = disk_space * MAX_SWAP_DISK_RATIO
        if swap > max_swap:
            log.info("Suggested swap size (%(swap)s) exceeds %(percent)d %% of "
                     "disk space, using %(percent)d %% of disk space (%(size)s) "
                     "instead.", {"percent": MAX_SWAP_DISK_RATIO * 100,
                                  "swap": swap,
                                  "size": max_swap})
            swap = max_swap

    if not quiet:
        log.info("Swap attempt of %s", swap)

    return swap


def find_optical_media(devicetree):
    """Find all devices with mountable optical media.

    Search for devices identified as cdrom along with any other
    device that has an iso9660 filesystem. This will catch USB
    media created from ISO images.

    :param devicetree: an instance of a device tree
    :return: a list of devices
    """
    devices = []

    for device in devicetree.devices:
        if device.type != "cdrom" and device.format.type != "iso9660":
            continue

        if not device.controllable:
            continue

        devicetree.handle_format(None, device)
        if not hasattr(device.format, "mount"):
            # no mountable media
            continue

        devices.append(device)

    return devices


def find_mountable_partitions(devicetree):
    """Find all mountable partitions.

    :param devicetree: an instance of a device tree
    :return: a list of devices
    """
    devices = []

    for device in devicetree.devices:
        if device.type != "partition":
            continue

        if not device.format.exists:
            continue

        if not device.format.mountable:
            continue

        devices.append(device)

    return devices


def unlock_device(storage, device, passphrase):
    """Unlock a LUKS device.

    :param storage: an instance of the storage
    :param device: a device to unlock
    :param passphrase: a passphrase to use
    :return: True if success, otherwise False
    """
    # Set the passphrase.
    device.format.passphrase = passphrase

    try:
        # Unlock the device.
        device.setup()
        device.format.setup()
    except StorageError as err:
        log.error("Failed to unlock %s: %s", device.name, err)

        # Teardown the device.
        device.teardown(recursive=True)

        # Forget the wrong passphrase.
        device.format.passphrase = None

        return False
    else:
        # Save the passphrase.
        storage.save_passphrase(device)

        # Wait for the device.
        # Otherwise, we could get a message about no Linux partitions.
        time.sleep(2)

        # Update the device tree.
        storage.devicetree.populate()
        storage.devicetree.teardown_all()

        return True


def find_unconfigured_luks(storage):
    """Find all unconfigured LUKS devices.

    Returns a list of devices that require a passphrase
    for their configuration.

    :param storage: an instance of Blivet
    :return: a list of devices
    """
    devices = []

    for device in storage.devices:
        # Only LUKS devices.
        if not device.format.type == "luks":
            continue

        # Skip existing formats.
        if device.format.exists:
            continue

        # Skip formats with keys.
        if device.format.has_key:
            continue

        devices.append(device)

    return devices


def setup_passphrase(storage, passphrase):
    """Set up the given passphrase on unconfigured LUKS devices.

    :param storage: an instance of Blivet
    :param passphrase: a passphrase to use
    """
    for device in find_unconfigured_luks(storage):
        device.format.passphrase = passphrase
        storage.save_passphrase(device)
