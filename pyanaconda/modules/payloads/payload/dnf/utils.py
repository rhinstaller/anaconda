#
# Copyright (C) 2020 Red Hat, Inc.
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
import fnmatch
import hashlib
import os

import rpm
from blivet.size import Size
from libdnf.transaction import TransactionItemState_ERROR

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.hw import is_lpae_available
from pyanaconda.core.path import join_paths
from pyanaconda.core.payload import parse_hdd_url
from pyanaconda.core.product import get_product_name, get_product_version
from pyanaconda.core.regexes import VERSION_DIGITS
from pyanaconda.core.util import execWithCapture
from pyanaconda.modules.common.constants.objects import DEVICE_TREE, DISK_SELECTION
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.modules.common.structures.packages import PackagesSelectionData
from pyanaconda.modules.payloads.base.utils import sort_kernel_version_list
from pyanaconda.modules.payloads.constants import SourceType

log = get_module_logger(__name__)

DNF_PACKAGE_CACHE_DIR_SUFFIX = 'dnf.package.cache'


def calculate_hash(data):
    """Calculate hash from the given data.

    :return: a string with the hash
    """
    m = hashlib.sha256()
    m.update(data.encode('ascii', 'backslashreplace'))
    return m.digest()


def get_kernel_package(dnf_manager, exclude_list):
    """Get an installable kernel package.

    :param dnf_manager: a DNF manager
    :param exclude_list: a list of excluded packages
    :return: a package name or None
    """
    if "kernel" in exclude_list:
        return None

    # Get the kernel packages.
    kernels = ["kernel"]

    # ARM systems use either the standard Multiplatform or LPAE platform.
    if is_lpae_available():
        kernels.insert(0, "kernel-lpae")

    # Find an installable one.
    for kernel_package in kernels:
        if kernel_package in exclude_list:
            continue

        if not dnf_manager.is_package_available(kernel_package):
            log.info("No such package: %s", kernel_package)
            continue

        return kernel_package

    log.error("Failed to select a kernel from: %s", kernels)
    return None


def get_product_release_version():
    """Get a release version of the product.

    :return: a string with the release version
    """
    try:
        release_version = VERSION_DIGITS.match(get_product_version()).group(1)
    except AttributeError:
        release_version = "rawhide"

    log.debug("Release version of %s is %s.", get_product_name(), release_version)
    return release_version


def get_installation_specs(data: PackagesSelectionData, default_environment=None):
    """Get specifications of packages, groups and modules for installation.

    :param data: a packages selection data
    :param default_environment: a default environment to install
    :return: a tuple of specification lists for inclusion and exclusion
    """
    # Note about package/group/module spec formatting:
    # - leading @ signifies a group or module
    # - no leading @ means a package
    include_list = []
    exclude_list = []

    # Handle the environment.
    if data.default_environment_enabled and default_environment:
        log.info("Selecting default environment '%s'.", default_environment)
        include_list.append("@{}".format(default_environment))
    elif data.environment:
        include_list.append("@{}".format(data.environment))

    # Handle the core group.
    if not data.core_group_enabled:
        log.info("Skipping @core group; system may not be complete.")
        exclude_list.append("@core")
    else:
        include_list.append("@core")

    # Handle groups.
    for group_name in data.excluded_groups:
        exclude_list.append("@{}".format(group_name))

    for group_name in data.groups:
        # Packages in groups can have different types
        # and we provide an option to users to set
        # which types are going to be installed.
        if group_name in data.groups_package_types:
            type_list = data.groups_package_types[group_name]
            group_spec = "@{group_name}/{types}".format(
                group_name=group_name,
                types=",".join(type_list)
            )
        else:
            # If group is a regular group this is equal to
            # @group/mandatory,default,conditional (current
            # content of the DNF GROUP_PACKAGE_TYPES constant).
            group_spec = "@{}".format(group_name)

        include_list.append(group_spec)

    # Handle packages.
    for pkg_name in data.excluded_packages:
        exclude_list.append(pkg_name)

    for pkg_name in data.packages:
        include_list.append(pkg_name)

    return include_list, exclude_list


def get_kernel_version_list():
    """Get a list of installed kernel versions.

    :return: a list of kernel versions
    """
    files = []
    efi_dir = conf.bootloader.efi_dir

    # Find all installed RPMs that provide 'kernel'.
    ts = rpm.TransactionSet(conf.target.system_root)
    mi = ts.dbMatch('providename', 'kernel')

    for hdr in mi:
        # Find all /boot/vmlinuz- files and strip off vmlinuz-.
        files.extend((
            f.split("/")[-1][8:] for f in hdr.filenames
            if fnmatch.fnmatch(f, "/boot/vmlinuz-*") or
            fnmatch.fnmatch(f, "/boot/efi/EFI/%s/vmlinuz-*" % efi_dir)
        ))

    # Sort the kernel versions.
    sort_kernel_version_list(files)

    return files


def get_free_space_map(current=True, scheduled=False):
    """Get the available file system disk space.

    :param bool current: use information about current mount points
    :param bool scheduled: use information about scheduled mount points
    :return: a dictionary of mount points and their available space
    """
    mount_points = {}

    if scheduled:
        mount_points.update(_get_scheduled_free_space_map())

    if current:
        mount_points.update(_get_current_free_space_map())

    return mount_points


def _get_current_free_space_map():
    """Get the available file system disk space of the current system.

    :return: a dictionary of mount points and their available space
    """
    mapping = {}

    # Generate the dictionary of mount points and sizes.
    output = execWithCapture('df', ['--output=target,avail'])
    lines = output.rstrip().splitlines()

    for line in lines:
        key, val = line.rsplit(maxsplit=1)

        if not key.startswith('/'):
            continue

        mapping[key] = Size(int(val) * 1024)

    # Add /var/tmp/ if this is a directory or image installation.
    if not conf.target.is_hardware:
        var_tmp = os.statvfs("/var/tmp")
        mapping["/var/tmp"] = Size(var_tmp.f_frsize * var_tmp.f_bfree)

    return mapping


def _get_scheduled_free_space_map():
    """Get the available file system disk space of the scheduled system.

    :return: a dictionary of mount points and their available space
    """
    device_tree = STORAGE.get_proxy(DEVICE_TREE)
    mount_points = {}

    for mount_point in device_tree.GetMountPoints():
        # we can ignore swap
        if not mount_point.startswith('/'):
            continue

        free_space = Size(
            device_tree.GetFileSystemFreeSpace([mount_point])
        )
        mount_point = os.path.normpath(
            conf.target.system_root + mount_point
        )
        mount_points[mount_point] = free_space

    return mount_points


def _pick_mount_points(mount_points, download_size, install_size):
    """Pick mount points for the package installation.

    :return: a set of sufficient mount points
    """
    suitable = {
        '/var/tmp',
        conf.target.system_root,
        join_paths(conf.target.system_root, 'home'),
        join_paths(conf.target.system_root, 'tmp'),
        join_paths(conf.target.system_root, 'var'),
    }

    sufficient = set()

    for mount_point, size in mount_points.items():
        # Ignore mount points that are not suitable.
        if mount_point not in suitable:
            continue

        if size >= (download_size + install_size):
            log.debug("Considering %s (%s) for download and install.", mount_point, size)
            sufficient.add(mount_point)

        elif size >= download_size and not mount_point.startswith(conf.target.system_root):
            log.debug("Considering %s (%s) for download.", mount_point, size)
            sufficient.add(mount_point)

    return sufficient


def _get_biggest_mount_point(mount_points, sufficient):
    """Get the biggest sufficient mount point.

    :return: a mount point or None
    """
    return max(sufficient, default=None, key=mount_points.get)


def pick_download_location(dnf_manager):
    """Pick the download location.

    :param dnf_manager: the DNF manager
    :return: a path to the download location
    """
    download_size = dnf_manager.get_download_size()
    install_size = dnf_manager.get_installation_size()
    mount_points = get_free_space_map()

    # Try to find mount points that are sufficient for download and install.
    sufficient = _pick_mount_points(
        mount_points,
        download_size,
        install_size
    )

    # Or find mount points that are sufficient only for download.
    if not sufficient:
        sufficient = _pick_mount_points(
            mount_points,
            download_size,
            install_size=0
        )

    # Ignore the system root if there are other mount points.
    if len(sufficient) > 1:
        sufficient.discard(conf.target.system_root)

    if not sufficient:
        raise RuntimeError(
            "Not enough disk space to download the "
            "packages; size {}.".format(download_size)
        )

    # Choose the biggest sufficient mount point.
    mount_point = _get_biggest_mount_point(mount_points, sufficient)

    log.info("Mount point %s picked as download location", mount_point)
    location = join_paths(mount_point, DNF_PACKAGE_CACHE_DIR_SUFFIX)

    return location


def calculate_required_space(dnf_manager):
    """Calculate the space required for the installation.

    :param DNFManager dnf_manager: the DNF manager
    :return Size: the required space
    """
    installation_size = dnf_manager.get_installation_size()
    download_size = dnf_manager.get_download_size()
    mount_points = get_free_space_map(scheduled=True)

    # Find sufficient mount points.
    sufficient = _pick_mount_points(
        mount_points,
        download_size,
        installation_size
    )

    # Choose the biggest sufficient mount point.
    mount_point = _get_biggest_mount_point(mount_points, sufficient)

    if not mount_point or mount_point.startswith(conf.target.system_root):
        log.debug("The install and download space is required.")
        required_space = installation_size + download_size
    else:
        log.debug("Use the %s mount point for the %s download.", mount_point, download_size)
        log.debug("Only the install space is required.")
        required_space = installation_size

    log.debug("The package installation requires %s.", required_space)
    return required_space


def collect_installation_devices(sources, repositories):
    """Collect devices of installation sources.

    :return: a list of device specifications
    """
    devices = set()

    configurations = [
        s.configuration
        for s in sources
        if s.type == SourceType.HDD
    ]

    for repository in configurations + repositories:
        if repository.url.startswith("hd:"):
            device, _path = parse_hdd_url(repository.url)
            devices.add(device)

    return devices


def protect_installation_devices(previous_devices, current_devices):
    """Protect installation devices.

    :param previous_devices: a list of device specifications
    :param current_devices: a list of device specifications
    """
    # Nothing has changed.
    if previous_devices == current_devices:
        return

    disk_selection_proxy = STORAGE.get_proxy(DISK_SELECTION)
    protected_devices = disk_selection_proxy.ProtectedDevices

    # Remove previous devices from the list.
    for spec in previous_devices:
        if spec in protected_devices:
            protected_devices.remove(spec)

    # Add current devices from the list.
    for spec in sorted(current_devices):
        if spec not in protected_devices:
            protected_devices.append(spec)

    disk_selection_proxy.ProtectedDevices = protected_devices


def transaction_has_errors(transaction):
    """Detect if finished DNF transaction has any errors.

    :param transaction: the DNF transaction
    :return: True if the transaction has any error, otherwise False
    """
    has_errors = False
    for tsi in transaction:
        if tsi.state == TransactionItemState_ERROR:
            log.error("The transaction contains item %s in error state.", tsi)
            has_errors = True
    return has_errors
