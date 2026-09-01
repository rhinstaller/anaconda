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
import glob
import hashlib
import os
import stat

import blivet.util
import requests

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.constants import NETWORK_CONNECTION_TIMEOUT
from pyanaconda.core.i18n import _
from pyanaconda.core.path import join_paths
from pyanaconda.core.string import lower_ascii
from pyanaconda.core.util import execReadlines, execWithRedirect, requests_session
from pyanaconda.modules.common.errors.installation import PayloadInstallationError
from pyanaconda.modules.common.structures.live_image import LiveImageConfigurationData
from pyanaconda.modules.common.task import Task
from pyanaconda.modules.payloads.payload.live_image.download_progress import (
    DownloadProgress,
)
from pyanaconda.modules.payloads.payload.live_image.installation_progress import (
    InstallationProgress,
)
from pyanaconda.modules.payloads.payload.live_image.utils import get_proxies_from_option

log = get_module_logger(__name__)


class DownloadImageTask(Task):
    """Task to download an image."""

    def __init__(self, configuration: LiveImageConfigurationData, download_path):
        """Create a new task.

        :param configuration: a configuration of a remote image
        :type configuration: an instance of LiveImageConfigurationData
        :param str download_path: a path to the downloaded image
        """
        super().__init__()
        self._url = configuration.url
        self._proxy = configuration.proxy
        self._ssl_verify = configuration.ssl_verification_enabled
        self._download_path = download_path

    @property
    def name(self):
        """Name of the task."""
        return "Download an image"

    def run(self):
        """Run the task.

        If the image is local, we return its local location. Otherwise,
        the image is downloaded at the specified download location and
        we return that one.

        :return: a path to the image
        """
        log.info("Downloading the image...")

        if self._url.startswith("file://"):
            log.info("Nothing to download.")
            return self._url.removeprefix("file://")

        with requests_session() as session:
            try:
                # Send a GET request to the image URL.
                response = self._send_request(session)

                # Download the image to a file.
                self._download_image(response)

            except requests.exceptions.RequestException as e:
                raise PayloadInstallationError(
                    "Error while downloading the image: {}".format(e)
                ) from e

        return self._download_path

    def _send_request(self, session):
        """Send a GET request to the image URL."""
        proxies = get_proxies_from_option(
            self._proxy
        )
        response = session.get(
            url=self._url,
            proxies=proxies,
            verify=self._ssl_verify,
            stream=True,
            timeout=NETWORK_CONNECTION_TIMEOUT,
        )
        response.raise_for_status()
        return response

    def _download_image(self, response):
        """Download the image to a file."""
        # Handle no content length header.
        if not self._get_content_length(response):
            download = self._direct_download
        else:
            download = self._stream_download

        # Download the image to a file.
        with open(self._download_path, "wb") as image_file:
            download(response, image_file)

    def _get_content_length(self, response):
        """Get the content length value."""
        return response.headers.get('content-length')

    def _direct_download(self, response, image_file):
        """Download the image at once."""
        log.warning(
            "content-length header is missing for the installation "
            "image, download progress reporting will not be available"
        )

        self.report_progress(_("Downloading {}").format(self._url))
        image_file.write(response.content)
        log.debug("Downloaded %s.", self._url)

    def _stream_download(self, response, image_file):
        """Download the image in 1 MB chunks."""
        total_size = int(self._get_content_length(response))

        progress = DownloadProgress(
            url=self._url,
            callback=self.report_progress,
            total_size=total_size,
        )

        progress.start()
        downloaded_size = 0

        for chunks in response.iter_content(1024 * 1024):
            if not chunks:
                continue

            image_file.write(chunks)
            image_file.flush()

            downloaded_size += len(chunks)
            progress.update(downloaded_size)

        progress.end()


class VerifyImageChecksumTask(Task):
    """Task to verify the checksum of the downloaded image."""

    def __init__(self, configuration: LiveImageConfigurationData, image_path):
        """Create a new task.

        :param configuration: a configuration of a remote image
        :type configuration: an instance of LiveImageConfigurationData
        :param image_path: a path to the image
        """
        super().__init__()
        self._image_path = image_path
        self._checksum = configuration.checksum

    @property
    def name(self):
        return "Check the image checksum"

    def run(self):
        """Run the task."""
        if not self._checksum:
            log.debug("No checksum to verify.")
            return

        self.report_progress(_("Checking image checksum"))
        expected_checksum = self._normalize_checksum(self._checksum)
        calculated_checksum = self._calculate_checksum(self._image_path)

        if expected_checksum != calculated_checksum:
            log.error("'%s' does not match '%s'", calculated_checksum, expected_checksum)
            raise PayloadInstallationError("Checksum of the image does not match.")

        log.debug("Checksum of the image does match.")

    @staticmethod
    def _normalize_checksum(checksum):
        """Normalize the given checksum."""
        return lower_ascii(checksum)

    @staticmethod
    def _calculate_checksum(file_path):
        """Calculate the file checksum."""
        sha256 = hashlib.sha256()

        with open(file_path, "rb") as f:
            while True:
                data = f.read(1024 * 1024)
                if not data:
                    break
                sha256.update(data)

        checksum = sha256.hexdigest()
        log.debug("sha256 of %s: %s", file_path, checksum)
        return checksum


class MountImageTask(Task):
    """Mount the image for the installation."""

    def __init__(self, image_path, image_mount_point, iso_mount_point):
        """Create a new task.

        :param image_path: a path to the downloaded image
        :param image_mount_point: a path to the image mount point
        :param iso_mount_point: a path to the ISO mount point
        """
        super().__init__()
        self._image_path = image_path
        self._image_mount_point = image_mount_point
        self._iso_mount_point = iso_mount_point

    @property
    def name(self):
        """The name of the task."""
        return "Mount the image"

    def run(self):
        """Run the task.

        :return: a path to the content that should be installed
        """
        self._make_root_rprivate()

        # Mount the downloaded image.
        self._mount_image(self._image_path, self._image_mount_point)

        # Mount the first .img in the LiveOS directory if any.
        iso_path = self._find_live_os_image()

        if iso_path:
            self._mount_image(iso_path, self._iso_mount_point)
            return self._iso_mount_point

        # Otherwise, use the downloaded image.
        return self._image_mount_point

    @staticmethod
    def _make_root_rprivate():
        """Make the mount of '/' rprivate.

        Work around inability to move shared filesystems. Also,
        do not share the image mounts with /run bind-mounted to
        physical target root during storage.mount_filesystems.
        """
        rc = execWithRedirect("mount", ["--make-rprivate", "/"])

        if rc != 0:
            raise PayloadInstallationError(
                "Failed to make the '/' mount rprivate: {}".format(rc)
            )

    def _mount_image(self, image_path, mount_point):
        """Mount the image."""
        try:
            rc = blivet.util.mount(
                image_path,
                mount_point,
                fstype="auto",
                options="ro"
            )
        except OSError as e:
            raise PayloadInstallationError(str(e)) from e

        if rc != 0:
            raise PayloadInstallationError(
                "Failed to mount '{}' at '{}': {}".format(image_path, mount_point, rc)
            )

    def _find_live_os_image(self):
        """See if there is a LiveOS/*.img style squashfs image.

        :return: a relative path to the image or None
        """
        if not os.path.exists(join_paths(self._image_mount_point, "LiveOS")):
            return None

        img_files = glob.glob(join_paths(self._image_mount_point, "LiveOS", "*.img"))

        if not img_files:
            return None

        return img_files[0]


class InstallFromTarTask(Task):
    """Task to install the payload from tarball."""

    def __init__(self, sysroot, tarfile):
        """Create a new task.

        :param sysroot: a path to the system root
        :param tarfile: a path to the tarball
        """
        super().__init__()
        self._sysroot = sysroot
        self._tarfile = tarfile

    @property
    def name(self):
        """The name of the task."""
        return "Install the payload from a tarball"

    @property
    def _installation_size(self):
        """The installation size of the archive.

        Use 2x the archive's size to estimate the size of the install.

        :return: a size in bytes
        """
        return os.stat(self._tarfile)[stat.ST_SIZE] * 2

    def run(self):
        """Run the task."""
        with self._monitor_progress():
            self._install_tar()

    def _monitor_progress(self):
        """Get a progress monitor."""
        return InstallationProgress(
            sysroot=self._sysroot,
            callback=self.report_progress,
            installation_size=self._installation_size,
        )

    def _install_tar(self):
        """Run installation of the payload from a tarball.

        Preserve ACL's, xattrs, and SELinux context.
        """
        cmd = "tar"
        args = [
            "--numeric-owner",
            "--selinux",
            "--acls",
            "--xattrs",
            "--xattrs-include", "*",
            "--exclude", "./dev/*",
            "--exclude", "./proc/*",
            "--exclude", "./tmp/*",
            "--exclude", "./sys/*",
            "--exclude", "./run/*",
            "--exclude", "./boot/*rescue*",
            "--exclude", "./boot/loader",
            "--exclude", "./boot/efi/loader",
            "--exclude", "./etc/machine-id",
            "--exclude", "./etc/machine-info",
            "-xaf", self._tarfile,
            "-C", self._sysroot
        ]

        try:
            execWithRedirect(cmd, args)
        except (OSError, RuntimeError) as e:
            msg = "Failed to install tar: {}".format(e)
            raise PayloadInstallationError(msg) from None


class InstallFromImageTask(Task):
    """Task to install the payload from image."""

    def __init__(self, sysroot, mount_point):
        """Create a new task.

        :param sysroot: a path to the system root
        :param mount_point: a path to the mounted image
        """
        super().__init__()
        self._sysroot = sysroot
        self._mount_point = mount_point

    @property
    def name(self):
        """The name of the task."""
        return "Install the payload from image"

    def run(self):
        """Run installation of the payload from image.

        Preserve permissions, owners, groups, ACL's, xattrs, times,
        symlinks and hardlinks. Go recursively, include devices and
        special files. Don't cross file system boundaries.

        Use a trailing slash on the source directory to copy the content
        instead of the directory itself. See `man rsync`.
        """
        # Force write everything to disk.
        self.report_progress(_("Synchronizing writes to disk"))
        os.sync()

        self.report_progress(_("Installing software..."))

        self._run_rsync(
            flags="-pogAXtlHrDx",
            excludes=[
                "/dev/",
                "/proc/",
                "/tmp/*",
                "/sys/",
                "/run/",
                "/boot/*rescue*",
                "/boot/loader/",
                "/boot/efi/",
                # Fixup: exclude paths that fail with lremovexattr(security.selinux) on KIWI-built
                # images. Remove after https://github.com/OSInside/kiwi-boxed-plugin/issues/99
                "/boot/grub2/",
                "/etc/sysconfig/",
                "/usr/lib/grub/",
                "/etc/machine-id",
                "/etc/machine-info",
            ],
            src=os.path.normpath(self._mount_point) + "/",
            dest=self._sysroot,
        )

        if os.path.exists(os.path.join(self._mount_point, "boot/efi")):
            # Handle /boot/efi separately due to FAT filesystem limitations
            # FAT cannot support permissions, ownership, symlinks, hard links,
            # xattrs, ACLs or modification times
            self._run_rsync(
                flags="-rx",
                excludes=["/boot/efi/loader/"],
                src=os.path.normpath(self._mount_point) + "/boot/efi/",
                dest=os.path.join(self._sysroot, "boot/efi"),
            )

        # Fixup: re-copy with -rx (no xattrs) paths that fail above on KIWI-built images.
        # Remove after https://github.com/OSInside/kiwi-boxed-plugin/issues/99 is fixed.
        for rel_src in ("boot/grub2", "etc/sysconfig", "usr/lib/grub"):
            src_dir = os.path.join(self._mount_point, rel_src)
            if not os.path.exists(src_dir):
                continue
            dest_dir = os.path.join(self._sysroot, rel_src)
            os.makedirs(dest_dir, exist_ok=True)
            self._run_rsync(
                flags="-rx",
                excludes=[],
                src=os.path.normpath(src_dir) + "/",
                dest=dest_dir,
            )

    def _run_rsync(self, flags, excludes, src, dest):
        """Run rsync with the given flags, excludes, source and destination.

        :param str flags: rsync option flags (e.g. "-pogAXtlHrDx" or "-rx")
        :param list excludes: list of exclude patterns
        :param str src: source path (should end with "/" to copy contents)
        :param str dest: destination path
        :raises PayloadInstallationError: if rsync fails
        """
        args = [flags, "--stats", "--no-inc-recursive"]
        for exc in excludes:
            args += ["--exclude", exc]
        args += [src, dest]

        try:
            # Log only the statistics section to avoid OOM on low-end systems
            # where the journal is written to overlay in memory.
            log_output = False
            for line in execReadlines("rsync", args):
                if not line.strip():
                    log_output = True
                    continue
                if log_output:
                    log.debug("rsync output: %s", line.strip())
        except OSError as e:
            raise PayloadInstallationError(
                "Failed to install {} from image: {}".format(src, e)
            ) from None


class RemoveImageTask(Task):
    """Task to remove the downloaded image."""

    def __init__(self, download_path):
        """Create a new task."""
        super().__init__()
        self._download_path = download_path

    @property
    def name(self):
        """Name of the task."""
        return "Remove the downloaded image"""

    def run(self):
        """Run the task."""
        if not os.path.exists(self._download_path):
            log.info("Nothing to remove.")
            return

        log.debug("Removing the downloaded image at %s.", self._download_path)
        os.unlink(self._download_path)
