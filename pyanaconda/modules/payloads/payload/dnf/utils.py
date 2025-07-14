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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import fnmatch
import hashlib

import rpm
from libdnf5 import comps
from libdnf5.transaction import TransactionItemState_ERROR

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core import constants
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.hw import is_lpae_available
from pyanaconda.core.payload import parse_hdd_url
from pyanaconda.core.product import get_product_name, get_product_version
from pyanaconda.core.regexes import VERSION_DIGITS
from pyanaconda.modules.common.constants.objects import DISK_SELECTION
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.modules.common.structures.packages import PackagesSelectionData
from pyanaconda.modules.payloads.base.utils import sort_kernel_version_list
from pyanaconda.modules.payloads.constants import SourceType

log = get_module_logger(__name__)


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


def get_group_package_types(spec):
    package_types = 0
    if spec.startswith("@") and '/' in spec:
        spec, types = spec.split('/')
        types = types.split(',')
        if constants.GROUP_PACKAGE_TYPE_MANDATORY in types:
            package_types += comps.PackageType_MANDATORY
        if constants.GROUP_PACKAGE_TYPE_CONDITIONAL in types:
            package_types += comps.PackageType_CONDITIONAL
        if constants.GROUP_PACKAGE_TYPE_DEFAULT in types:
            package_types += comps.PackageType_DEFAULT
        if constants.GROUP_PACKAGE_TYPE_OPTIONAL in types:
            package_types += comps.PackageType_OPTIONAL
    return spec, package_types


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
    for environment in transaction.get_transaction_environments():
        if environment.get_state() == TransactionItemState_ERROR:
            log.error("The transaction contains environment %s in error state.", environment)
            has_errors = True
    for group in transaction.get_transaction_groups():
        if group.get_state() == TransactionItemState_ERROR:
            log.error("The transaction contains group %s in error state.", group)
            has_errors = True
    for package in transaction.get_transaction_packages():
        if package.get_state() == TransactionItemState_ERROR:
            log.error("The transaction contains package %s in error state.", package)
            has_errors = True
    return has_errors
