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
import time

import requests
from blivet import udev
from blivet.errors import StorageError
from blivet.formats import device_formats
from blivet.formats.fs import FS
from blivet.size import Size
from bytesize.bytesize import ROUND_HALF_UP
from pykickstart.errors import KickstartError

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core import util
from pyanaconda.core.i18n import _
from pyanaconda.modules.common.constants.services import NETWORK

log = get_module_logger(__name__)


def get_supported_filesystems():
    """Get the supported filesystems.

    :return: a list of formats
    """
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
        raise KickstartError(_("SSL error while downloading the escrow certificate:\n\n%s") % e) \
            from e
    except requests.exceptions.RequestException as e:
        raise KickstartError(_("The following error was encountered while downloading the "
                               "escrow certificate:\n\n%s") % e) from e

    try:
        certificate = request.content
    finally:
        request.close()

    return certificate


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
