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
import dnf.subject
import dnf.const
import fnmatch
import os
import rpm

from blivet.size import Size

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core import util
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.regexes import VERSION_DIGITS
from pyanaconda.core.util import is_lpae_available, decode_bytes, join_paths, execWithCapture
from pyanaconda.modules.common.structures.packages import PackagesSelectionData
from pyanaconda.product import productName, productVersion
from pyanaconda.modules.payloads.base.utils import sort_kernel_version_list

log = get_module_logger(__name__)

DNF_PACKAGE_CACHE_DIR_SUFFIX = 'dnf.package.cache'


def get_default_environment(dnf_manager):
    """Get a default environment.

    :return: an id of an environment or None
    """
    environments = dnf_manager.environments

    if environments:
        return environments[0]

    return None


def get_kernel_package(dnf_base, exclude_list):
    """Get an installable kernel package.

    :param dnf_base: a DNF base
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
        subject = dnf.subject.Subject(kernel_package)
        installable = bool(subject.get_best_query(dnf_base.sack))

        if installable:
            log.info("kernel: selected %s", kernel_package)
            return kernel_package

        log.info("kernel: no such package %s", kernel_package)

    log.error("kernel: failed to select a kernel from %s", kernels)
    return None


def get_product_release_version():
    """Get a release version of the product.

    :return: a string with the release version
    """
    try:
        release_version = VERSION_DIGITS.match(productVersion).group(1)
    except AttributeError:
        release_version = "rawhide"

    log.debug("Release version of %s is %s.", productName, release_version)
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
        env = default_environment
        log.info("selecting default environment: %s", env)
        include_list.append("@{}".format(env))
    elif data.environment:
        env = data.environment
        log.info("selected environment: %s", env)
        include_list.append("@{}".format(env))

    # Handle the core group.
    if not data.core_group_enabled:
        log.info("skipping core group due to %%packages "
                 "--nocore; system may not be complete")
        exclude_list.append("@core")
    else:
        log.info("selected group: core")
        include_list.append("@core")

    # Handle groups.
    for group_name in data.excluded_groups:
        log.debug("excluding group %s", group_name)
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

        log.info("selected group: %s", group_name)
        include_list.append(group_spec)

    # Handle packages.
    for pkg_name in data.excluded_packages:
        log.info("excluded package: %s", pkg_name)
        exclude_list.append(pkg_name)

    for pkg_name in data.packages:
        log.info("selected package: %s", pkg_name)
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
        unicode_fnames = (decode_bytes(f) for f in hdr.filenames)

        # Find all /boot/vmlinuz- files and strip off vmlinuz-.
        files.extend((
            f.split("/")[-1][8:] for f in unicode_fnames
            if fnmatch.fnmatch(f, "/boot/vmlinuz-*") or
            fnmatch.fnmatch(f, "/boot/efi/EFI/%s/vmlinuz-*" % efi_dir)
        ))

    # Sort the kernel versions.
    sort_kernel_version_list(files)

    return files


def get_df_map():
    """Get the file system disk space usage.

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


def pick_mount_point(mount_points, download_size, install_size, download_only=False):
    """Pick a mount point for the package installation.

    :param mount_points: a dictionary of mount points and their available spaces
    :param download_size: a total size required for the package download
    :param install_size: a total size required for the package installation
    :param download_only: pick a mount point only for the package download
    :return: a mount point or None
    """
    log.info("Pick a mount point for %s download, %s install, %s total.",
             download_size, install_size, download_size + install_size)

    # Find sufficient mount points.
    sufficient = _pick_mount_points(
        mount_points,
        download_size,
        install_size
    )

    # Or find sufficient mount points specifically for the download.
    if download_only:

        # Ignore the installation size.
        if not sufficient:
            sufficient = _pick_mount_points(
                mount_points,
                download_size,
                install_size=0
            )

        # Ignore the system root if there are other mount points.
        if len(sufficient) > 1:
            sufficient.discard(conf.target.system_root)

    # Choose the biggest sufficient mount point.
    mount_point = max(sufficient, default=None, key=mount_points.get)

    log.info("Pick a sufficient mount point: %s", mount_point)
    return mount_point


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

        if size > (download_size + install_size):
            sufficient.add(mount_point)

        elif mount_point != conf.target.system_root and size > download_size:
            sufficient.add(mount_point)

    return sufficient


def pick_download_location(dnf_manager):
    """Pick the download location.

    :param dnf_manager: the DNF manager
    :return: a path to the download location
    """
    download_size = dnf_manager.get_download_size()
    install_size = dnf_manager.get_installation_size()
    mount_points = get_df_map()

    path = pick_mount_point(
        mount_points,
        download_size,
        install_size,
        download_only=True
    )

    if path is None:
        raise RuntimeError(
            "Not enough disk space to download the "
            "packages; size {}.".format(download_size)
        )

    log.info("Mount point %s picked as download location", path)
    location = util.join_paths(path, DNF_PACKAGE_CACHE_DIR_SUFFIX)

    return location
