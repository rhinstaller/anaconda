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


def get_mount_device(mountpoint):
    if os.path.ismount(mountpoint):
        return blivet.util.get_mount_device(mountpoint)


def get_mount_paths(device_path):
    return blivet.util.get_mount_paths(device_path)


def unmount(mountpoint, raise_exc=False):
    try:
        blivet.util.umount(mountpoint)
    except OSError as e:
        log.error(str(e))
        log.info("umount failed -- mounting on top of it")
        if raise_exc:
            raise


def mount(url, mountpoint, fstype, options):
    try:
        return blivet.util.mount(url, mountpoint, fstype=fstype, options=options)
    except OSError as e:
        raise PayloadSetupError(str(e))


def arch_is_x86():
    return blivet.arch.is_x86(32)


def arch_is_arm():
    return blivet.arch.is_arm()


def version_cmp(v1, v2):
    """Compare two version number strings."""
    first_version = LooseVersion(v1)
    second_version = LooseVersion(v2)
    return (first_version > second_version) - (first_version < second_version)
