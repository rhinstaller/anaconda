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
import os
import os.path
import stat

import blivet.util
from blivet.arch import get_arch
from blivet.util import mount
from productmd import DiscInfo

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.constants import SOURCES_DIR
from pyanaconda.core.path import join_paths
from pyanaconda.core.storage import device_matches
from pyanaconda.modules.payloads.payload.dnf.tree_info import (
    TreeInfoMetadata,
    TreeInfoMetadataError,
)

log = get_module_logger(__name__)

ISO_BLOCK_SIZE = 2048


def is_tar(url):
    """Is the given URL a path to the tarball?

    :param url: a string with URL
    :return: True or False
    """
    if not url:
        return False

    tar_suffixes = (".tar", ".tbz", ".tgz", ".txz", ".tar.bz2", ".tar.gz", ".tar.xz")
    return any(url.endswith(s) for s in tar_suffixes)


def has_network_protocol(url):
    """Does the given URL have a network protocol?

    :param url: a string with URL
    :return: True or False
    """
    if not url:
        return False

    network_protocols = ["http:", "https:", "ftp:", "nfs:"]
    return any(url.startswith(p) for p in network_protocols)


def is_valid_install_disk(tree_dir):
    """Is the disk a valid installation repository?

    Success criteria:
    - Disk must be already mounted at tree_dir.
    - A .discinfo file exists.
    - Third line of .discinfo equals current architecture.

    :param str tree_dir: Where the disk is mounted.
    :rtype: bool
    """
    try:
        with open(join_paths(tree_dir, ".discinfo"), "r") as f:
            f.readline()  # throw away timestamp
            f.readline()  # throw away description
            arch = f.readline().strip()
            if arch == get_arch():
                return True
    except OSError:
        pass
    return False


def find_and_mount_device(device_spec, mount_point):
    """Resolve what device to mount and do so, read-only.

    Assumes that the device is directly mountable without any preparations or dependencies.

    :param str device_spec: specification of the device
    :param str mount_point: where to mount the device

    :return: success or not
    :rtype: bool
    """
    matches = device_matches(device_spec)
    if not matches:
        log.error("Device spec %s does not resolve to anything", device_spec)
        return False

    device_path = "/dev/" + matches[0]

    try:
        mount(device=device_path,
              mountpoint=mount_point,
              fstype="auto",
              options="defaults,ro")
        return True
    except OSError as e:
        log.error("Mount of device failed: %s", e)
        return False


def find_and_mount_iso_image(source_path, mount_path):
    """Find ISO image and mount it.

    :param str source_path: path to where to look for the iso; it could point to iso directly
    :param str mount_path: where to mount the ISO image
    :return: name of the ISO image file or empty string if ISO can't be used
    """
    iso_name = _find_first_iso_image(source_path)

    if iso_name:
        path_to_iso = _create_iso_path(source_path, iso_name)

        if mount_iso_image(path_to_iso, mount_path):
            return iso_name

    return ""


def _find_first_iso_image(path, mount_path="/mnt/install/cdimage"):
    """Find the first iso image in path.

    :param str path: path to the directory with iso image(s); this also supports pointing to
        a specific .iso image
    :param str mount_path: path for mounting the ISO when checking it is valid

    FIXME once payloads are modularized:
      - mount_path should lose the legacy default

    :return: basename of the image - file name without path
    :rtype: str or None
    """
    try:
        os.stat(path)
    except OSError:
        return None

    arch = get_arch()
    discinfo_path = os.path.join(mount_path, ".discinfo")

    if os.path.isfile(path) and path.endswith(".iso"):
        files = [os.path.basename(path)]
        path = os.path.dirname(path)
    else:
        files = os.listdir(path)

    for fn in files:
        what = os.path.join(path, fn)
        log.debug("Checking %s", what)
        if not _is_iso_image(what):
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


def _is_iso_image(path):
    """Determine if a file is an ISO image or not.

    :param path: the full path to a file to check
    :return: True if ISO image, False otherwise
    """
    try:
        with open(path, "rb") as iso_file:
            for block_num in range(16, 100):
                iso_file.seek(block_num * ISO_BLOCK_SIZE + 1)
                if iso_file.read(5) == b"CD001":
                    return True
    except OSError:
        pass

    return False


def _check_repodata(mount_path):
    try:
        tree_info_metadata = TreeInfoMetadata()
        tree_info_metadata.load_file(mount_path)
        return tree_info_metadata.verify_image_base_repo()
    except TreeInfoMetadataError as e:
        log.debug("Can't read install tree metadata: %s", str(e))
        return False


def mount_iso_image(image_path, mount_point):
    """Mount ISO image.

    :param str image_path: where the image ISO file is
    :param str mount_point: where to mount the image

    :return: success or not
    :rtype: bool
    """
    try:
        mount(image_path, mount_point, fstype='iso9660', options="ro")
        return True
    except OSError as e:
        log.error("Mount of ISO file failed: %s", e)
        return False


def _create_iso_path(path, iso_name):
    """Get path to the ISO with the iso_name and path to the ISO.

    The problem of this is that path could point to the ISO directly. So this way
    we want to avoid situations like /abc/dvd.iso/dvd.iso

    :param str path: path where the iso is or path to the iso image file
    :param str iso_name: name of the iso
    :return: path to the iso image
    :rtype: str
    """
    # The directory parameter is not pointing directly to ISO
    if not path.endswith(iso_name):
        return os.path.normpath(join_paths(path, iso_name))

    # The directory parameter is pointing directly to ISO
    return path


def verify_valid_repository(path):
    """Check if the given path is a valid repository.

    :param str path: path to the repository
    :returns: True if repository is valid false otherwise
    :rtype: bool
    """
    repomd_path = join_paths(path, "repodata/repomd.xml")

    if os.path.exists(repomd_path) and os.path.isfile(repomd_path):
        return True

    # FIXME: Remove this temporary solution when payload source migration will be finished.
    #
    # Source should not point to an installation tree but only to a repository, however, right now
    # we are in state that sources are only for base repository and just reflecting data from
    # user. With the unified feature the above check won't work because repository is a sub-folder
    # redirected by .treeinfo file. Add this check back to fix this issue.
    if os.path.exists(join_paths(path, ".treeinfo")):
        return True
    if os.path.exists(join_paths(path, "treeinfo")):
        return True

    return False


class MountPointGenerator:
    _counter = 0

    @classmethod
    def generate_mount_point(cls, suffix):
        """Generate a complete unique mount point path

        The path includes an auto-incremented serial number and suffix.

        :param str suffix: Suffix of the mount point path
        :return:
        :rtype: str
        """
        path = "{}/mount-{:0>4}-{}".format(
            SOURCES_DIR,
            cls._counter,
            suffix
        )
        cls._counter = cls._counter + 1
        return path
