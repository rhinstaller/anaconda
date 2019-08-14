# Small utilities used in the payload by multiple places.
#
# Copyright (C) 2019  Red Hat, Inc.
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
import os
import blivet.util
import blivet.arch

from distutils.version import LooseVersion

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.payload.errors import PayloadSetupError

log = get_module_logger(__name__)


def resolve_device(storage, dev_spec):
    """Get the device matching the provided device specification.

    :param storage: an instance of Blivet's storage
    :param dev_spec: a string describing a block device
    :return: an instance of a device or None
    """
    return storage.devicetree.resolve_device(dev_spec)


def setup_device(device):
    """Open, or set up, a device.

    :param device: an instance of a device
    """
    device.setup()


def mount_device(device, mount_point):
    """Mount a filesystem on the device.

    :param device: an instance of a device
    :param mount_point: a path to the mount point
    """
    device.format.mount(mountpoint=mount_point)


def unmount_device(device, mount_point):
    """Unmount a filesystem on the device.

    :param device: an instance of a device
    :param mount_point: a path to the mount point or None
    """
    device.format.unmount(mountpoint=mount_point)


def teardown_device(device):
    """Close, or tear down, a device.

    :param device: an instance of a device
    """
    device.teardown(recursive=True)


def get_mount_device(mount_point):
    """Given a mount point, return the device node path mounted there.

    :param mount_point: a mount point
    :return: a device path or None
    """
    if os.path.ismount(mount_point):
        return blivet.util.get_mount_device(mount_point)

    return None


def get_mount_paths(device_path):
    """Given a device node path, return a list of all active mount points.

    :param device_path: a device path
    :return: a list of mount points
    """
    return blivet.util.get_mount_paths(device_path)


def unmount(mount_point, raise_exc=False):
    """Unmount a filesystem.

    :param mount_point: a mount point
    :param raise_exc: raise an exception if it fails
    """
    try:
        blivet.util.umount(mount_point)
    except OSError as e:
        log.error(str(e))
        log.info("umount failed -- mounting on top of it")
        if raise_exc:
            raise


def mount(device_path, mount_point, fstype, options):
    """Mount a filesystem.

    :param device_path: a device path
    :param mount_point: a mount point
    :param fstype: a filesystem type
    :param options: a string of mount options
    """
    try:
        return blivet.util.mount(device_path, mount_point, fstype=fstype, options=options)
    except OSError as e:
        raise PayloadSetupError(str(e))


def arch_is_x86():
    """Does the hardware support X86?"""
    return blivet.arch.is_x86(32)


def arch_is_arm():
    """Does the hardware support ARM?"""
    return blivet.arch.is_arm()


def version_cmp(v1, v2):
    """Compare two version number strings."""
    first_version = LooseVersion(v1)
    second_version = LooseVersion(v2)
    return (first_version > second_version) - (first_version < second_version)
