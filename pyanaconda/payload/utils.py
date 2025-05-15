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

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.modules.common.constants.objects import DEVICE_TREE
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.modules.common.structures.storage import DeviceData
from pyanaconda.payload.errors import PayloadSetupError

log = get_module_logger(__name__)


def resolve_device(dev_spec):
    """Get the device matching the provided device specification.

    :param str dev_spec: a string describing a block device
    :return: a device name or None
    """
    device_tree = STORAGE.get_proxy(DEVICE_TREE)
    return device_tree.ResolveDevice(dev_spec) or None


def get_device_path(device_name):
    """Return a device path.

    :param device_name: a device name
    :return: a device path
    """
    if device_name is None:
        return None

    device_tree = STORAGE.get_proxy(DEVICE_TREE)
    device_data = DeviceData.from_structure(device_tree.GetDeviceData(device_name))
    return device_data.path


def setup_device(device_name):
    """Open, or set up, a device.

    :param device_name: a device name
    """
    device_tree = STORAGE.get_proxy(DEVICE_TREE)
    device_tree.SetupDevice(device_name)


def mount_device(device_name, mount_point):
    """Mount a filesystem on the device.

    :param device_name: a device name
    :param str mount_point: a path to the mount point
    """
    device_tree = STORAGE.get_proxy(DEVICE_TREE)
    device_tree.MountDevice(device_name, mount_point, "ro")


def unmount_device(device_name, mount_point):
    """Unmount a filesystem on the device.

    FIXME: Always specify the mount point.

    :param device_name: a device name
    :param str mount_point: a path to the mount point or None
    """
    if not mount_point:
        device_path = get_device_path(device_name)
        mount_paths = get_mount_paths(device_path)

        if not mount_paths:
            return

        mount_point = mount_paths[-1]

    device_tree = STORAGE.get_proxy(DEVICE_TREE)
    device_tree.UnmountDevice(device_name, mount_point)


def teardown_device(device_name):
    """Close, or tear down, a device.

    :param device_name: a device name
    """
    device_tree = STORAGE.get_proxy(DEVICE_TREE)
    device_tree.TeardownDevice(device_name)


def get_mount_points():
    """Get mount points in the device tree.

    :return: a dictionary of mount points and device names
    """
    device_tree = STORAGE.get_proxy(DEVICE_TREE)
    return device_tree.GetMountPoints()


def get_mount_device_path(mount_point):
    """Given a mount point, return the device node path mounted there.

    :param str mount_point: a mount point
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

    :param str mount_point: a mount point
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

    :param str device_path: a device path
    :param str mount_point: a mount point
    :param str fstype: a filesystem type
    :param str options: mount options
    """
    try:
        return blivet.util.mount(device_path, mount_point, fstype=fstype, options=options)
    except OSError as e:
        raise PayloadSetupError(str(e)) from e
