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
import os.path

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.payload import parse_nfs_url
from pyanaconda.core.util import join_paths
from pyanaconda.modules.common.errors.payload import SourceSetupError
from pyanaconda.modules.common.task import Task
from pyanaconda.modules.payloads.source.utils import find_and_mount_iso_image, \
    verify_valid_repository
from pyanaconda.payload.errors import PayloadSetupError
from pyanaconda.payload.utils import mount, unmount

log = get_module_logger(__name__)

__all__ = ["SetUpNFSSourceTask"]


class SetUpNFSSourceTask(Task):
    """Task to set up the NFS source."""

    def __init__(self, device_mount, iso_mount, url):
        super().__init__()
        self._device_mount = device_mount
        self._iso_mount = iso_mount
        self._url = url

    @property
    def name(self):
        return "Set up NFS installation source"

    def run(self):
        """Set up the installation source."""
        log.debug("Setting up NFS source: %s", self._url)

        for mount_point in [self._device_mount, self._iso_mount]:
            if os.path.ismount(mount_point):
                raise SourceSetupError("The mount point {} is already in use.".format(
                    mount_point
                ))

        options, host, path = parse_nfs_url(self._url)
        path, image = self._split_iso_from_path(path)
        try:
            self._mount_nfs(host, options, path)
        except PayloadSetupError as exn:
            raise SourceSetupError("Could not mount NFS url '{}'".format(self._url)) from exn

        iso_source_path = join_paths(self._device_mount, image) if image else self._device_mount

        iso_name = find_and_mount_iso_image(iso_source_path, self._iso_mount)

        if iso_name:
            log.debug("Using the ISO '%s' mounted at '%s'.", iso_name, self._iso_mount)
            return self._iso_mount

        if verify_valid_repository(self._device_mount):
            log.debug("Using the directory at '%s'.", self._device_mount)
            return self._device_mount

        # nothing found unmount the existing device
        unmount(self._device_mount)
        raise SourceSetupError(
            "Nothing useful found for NFS source at {}".format(self._url))

    @staticmethod
    def _split_iso_from_path(path):
        """Split ISO from NFS path.

        NFS path could also contain pointer to ISO which should be mounted. Problem of this
        is that NFS path with ISO cannot be mounted as NFS mount. We have to split these
        before mount.

        :param path: path on the NFS server which could point to ISO
        :return: tuple of path, iso_file_name; is_file_name is empty if no ISO is part of the path
        :rtype: tuple (str, str)
        """
        if path.endswith(".iso"):
            return path.rsplit("/", maxsplit=1)

        return path, ""

    def _mount_nfs(self, host, options, path):
        if not options:
            options = "nolock"
        elif "nolock" not in options:
            options += ",nolock"

        mount("{}:{}".format(host, path), self._device_mount, fstype="nfs", options=options)
