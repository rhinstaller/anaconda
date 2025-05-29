#
# Utility functions shared for the whole payload module.
#
# Copyright (C) 2019 Red Hat, Inc.
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
import os
from functools import partial

from blivet.size import Size

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import NETWORK_CONNECTION_TIMEOUT, USER_AGENT
from pyanaconda.core.path import join_paths
from pyanaconda.core.payload import ProxyString, ProxyStringError, rpm_version_key
from pyanaconda.core.util import execWithCapture
from pyanaconda.modules.common.constants.objects import DEVICE_TREE
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.modules.common.structures.payload import RepoConfigurationData

log = get_module_logger(__name__)


def sort_kernel_version_list(kernel_version_list):
    """Sort the given kernel version list."""
    kernel_version_list.sort(key=rpm_version_key)


def get_downloader_for_repo_configuration(session, data: RepoConfigurationData):
    """Get a configured session.get method.

    :return: a partial function
    """
    # Prepare the SSL configuration.
    ssl_enabled = conf.payload.verify_ssl and data.ssl_verification_enabled

    # ssl_verify can be:
    #   - the path to a cert file
    #   - True, to use the system's certificates
    #   - False, to not verify
    ssl_verify = data.ssl_configuration.ca_cert_path or ssl_enabled

    # ssl_cert can be:
    #   - a tuple of paths to a client cert file and a client key file
    #   - None
    ssl_client_cert = data.ssl_configuration.client_cert_path or None
    ssl_client_key = data.ssl_configuration.client_key_path or None
    ssl_cert = (ssl_client_cert, ssl_client_key) if ssl_client_cert else None

    # Prepare the proxy configuration.
    proxy_url = data.proxy or None
    proxies = {}

    if proxy_url:
        try:
            proxy = ProxyString(proxy_url)
            proxies = {
                "http": proxy.url,
                "https": proxy.url,
                "ftp": proxy.url
            }
        except ProxyStringError as e:
            log.debug("Failed to parse the proxy '%s': %s", proxy_url, e)

    # Prepare headers.
    headers = {"user-agent": USER_AGENT}

    # Return a partial function.
    return partial(
        session.get,
        headers=headers,
        proxies=proxies,
        verify=ssl_verify,
        cert=ssl_cert,
        timeout=NETWORK_CONNECTION_TIMEOUT
    )


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


def pick_download_location(download_size, install_size, cache_dir_suffix):
    """Pick a download location

    :param dnf_manager: the DNF manager
    :return: a path to the download location
    """
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
    location = join_paths(mount_point, cache_dir_suffix)

    return location


def calculate_required_space(download_size, installation_size):
    """Calculate the space required for the installation.

    This takes into account whether the download location is part of the installed
    system or not.

    :param Size download_size: the download size
    :param Size installation_size: the installation size
    :return Size: the required space
    """
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
