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
import time
import requests

from blivet import udev
from blivet.size import Size
from blivet.errors import StorageError
from blivet.formats import device_formats
from blivet.formats.fs import FS
from blivet.formats.luks import LUKS2PBKDFArgs
from bytesize.bytesize import ROUND_HALF_UP

from pykickstart.errors import KickstartError

from pyanaconda.core import util
from pyanaconda.core.i18n import _, P_
from pyanaconda.modules.common.constants.services import NETWORK

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


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

        if not selected:
            errors.append(_("The selected disk {} is not recognized.").format(name))
            continue

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

        # Set the passphrase also to the original format of the device.
        device.original_format.passphrase = passphrase

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
