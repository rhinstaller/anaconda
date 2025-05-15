#
# image.py: Support methods for CD/DVD and ISO image installations.
#
# Copyright (C) 2007  Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import os
import os.path
import stat
import tempfile

import blivet.arch
import blivet.util
from blivet.size import Size
from productmd.discinfo import DiscInfo

from pyanaconda import isys
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.modules.common.constants.objects import DEVICE_TREE
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.modules.common.errors.storage import MountFilesystemError
from pyanaconda.modules.common.structures.storage import DeviceData, DeviceFormatData
from pyanaconda.payload import utils as payload_utils
from pyanaconda.payload.install_tree_metadata import InstallTreeMetadata

log = get_module_logger(__name__)

_arch = blivet.arch.get_arch()


def find_first_iso_image(path, mount_path="/mnt/install/cdimage"):
    """Find the first iso image in path.

    :param str path: path to the directory with iso image(s); this also supports pointing to
        a specific .iso image
    :param str mount_path: path for mounting the ISO when checking it is valid

    FIXME once payloads are modularized:
      - this should move somewhere else
      - mount_path should lose the legacy default

    :return: basename of the image - file name without path
    :rtype: str or None
    """
    try:
        os.stat(path)
    except OSError:
        return None

    arch = _arch
    discinfo_path = os.path.join(mount_path, ".discinfo")

    if os.path.isfile(path) and path.endswith(".iso"):
        files = [os.path.basename(path)]
        path = os.path.dirname(path)
    else:
        files = os.listdir(path)

    for fn in files:
        what = os.path.join(path, fn)
        log.debug("Checking %s", what)
        if not isys.isIsoImage(what):
            continue

        log.debug("Mounting %s on %s", what, mount_path)
        try:
            blivet.util.mount(what, mount_path, fstype="iso9660", options="ro")
        except OSError:
            continue

        if not os.access(discinfo_path, os.R_OK):
            blivet.util.umount(mount_path)
            continue

        log.debug("Reading .discinfo")
        disc_info = DiscInfo()

        # TODO replace next 2 blocks with:
        #   pyanaconda.modules.payloads.source.utils.is_valid_install_disk
        try:
            disc_info.load(discinfo_path)
            disc_arch = disc_info.arch
        except Exception as ex:  # pylint: disable=broad-except
            log.warning(".discinfo file can't be loaded: %s", ex)
            continue

        log.debug("discArch = %s", disc_arch)
        if disc_arch != arch:
            log.warning("Architectures mismatch in find_first_iso_image: %s != %s",
                        disc_arch, arch)
            blivet.util.umount(mount_path)
            continue

        # If there's no repodata, there's no point in trying to
        # install from it.
        if not _check_repodata(mount_path):
            log.warning("%s doesn't have a valid repodata, skipping", what)
            blivet.util.umount(mount_path)
            continue

        # warn user if images appears to be wrong size
        if os.stat(what)[stat.ST_SIZE] % 2048:
            log.warning(
                "The ISO image %s has a size which is not "
                "a multiple of 2048 bytes. This may mean it "
                "was corrupted on transfer to this computer.",
                what
            )
            blivet.util.umount(mount_path)
            continue

        log.info("Found disc at %s", fn)
        blivet.util.umount(mount_path)
        return fn

    return None


def _check_repodata(mount_path):
    install_tree_meta = InstallTreeMetadata()
    if not install_tree_meta.load_file(mount_path):
        log.warning("Can't read install tree metadata!")

    repo_md = install_tree_meta.get_base_repo_metadata()

    if not repo_md:
        repo_mds = install_tree_meta.get_metadata_repos()
        repo_md = _search_for_install_root_repository(repo_mds)

    if not repo_md:
        log.debug("There is no usable repository available")
        return False

    if repo_md.is_valid():
        return True

    log.debug("There is no valid repository available.")
    return False


def _search_for_install_root_repository(repos):
    for repo in repos:
        if repo.relative_path == ".":
            return repo

    return None


def find_optical_install_media():
    """Find a device with a valid optical install media.

    Return the first device containing a valid optical install
    media for this product.

    FIXME: This is duplicated in SetUpCdromSourceTask.run

    :return: a device name or None
    """
    device_tree = STORAGE.get_proxy(DEVICE_TREE)

    for dev in device_tree.FindOpticalMedia():
        mountpoint = tempfile.mkdtemp()

        try:
            try:
                payload_utils.mount_device(dev, mountpoint)
            except MountFilesystemError:
                continue
            try:
                from pyanaconda.modules.payloads.source.utils import (
                    is_valid_install_disk,
                )
                if not is_valid_install_disk(mountpoint):
                    continue
            finally:
                payload_utils.unmount_device(dev, mountpoint)
        finally:
            os.rmdir(mountpoint)

        return dev

    return None


def find_potential_hdiso_sources():
    """Find potential HDISO sources.

    Return a generator yielding Device instances that may have HDISO install
    media somewhere. Candidate devices are simply any that we can mount.

    :return: a list of device names
    """
    device_tree = STORAGE.get_proxy(DEVICE_TREE)
    return device_tree.FindMountablePartitions()


def get_hdiso_source_info(device_tree, device_name):
    """Get info about a potential HDISO source.

    :param device_tree: a proxy of a device tree
    :param device_name: a device name
    :return: a dictionary with a device info
    """
    device_data = DeviceData.from_structure(
        device_tree.GetDeviceData(device_name)
    )

    format_data = DeviceFormatData.from_structure(
        device_tree.GetFormatData(device_name)
    )

    disk_data = DeviceData.from_structure(
        device_tree.GetDeviceData(device_data.parents[0])
    )

    return {
        "model": disk_data.attrs.get("model", "").replace("_", " "),
        "path": device_data.path,
        "size": Size(device_data.size),
        "format": format_data.description,
        "label": format_data.attrs.get("label") or format_data.attrs.get("uuid") or ""
    }


def get_hdiso_source_description(device_info):
    """Get a description of a potential HDISO source.

    :param device_info: a dictionary with a device info
    :return: a string with a device description
    """
    return "{model} {path} ({size}) {format} {label}".format(**device_info)
