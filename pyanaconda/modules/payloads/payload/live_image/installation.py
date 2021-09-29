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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import hashlib

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.i18n import _
from pyanaconda.core.util import execWithRedirect
from pyanaconda.core.string import lower_ascii
from pyanaconda.modules.common.task import Task
from pyanaconda.modules.common.errors.installation import PayloadInstallationError

log = get_module_logger(__name__)


class VerifyImageChecksum(Task):
    """Task to verify the checksum of the downloaded image."""

    def __init__(self, image_path, checksum):
        """Create a new task.

        :param image_path: a path to the image
        :param checksum: an expected sha256 checksum
        """
        super().__init__()
        self._image_path = image_path
        self._checksum = checksum

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
        print(checksum)
        return checksum


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
        return "Install the payload from a tarball"

    def run(self):
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
        return "Install the payload from image"

    def run(self):
        """Run installation of the payload from image.

        Preserve permissions, owners, groups, ACL's, xattrs, times,
        symlinks and hardlinks. Go recursively, include devices and
        special files. Don't cross file system boundaries.
        """
        cmd = "rsync"
        args = [
            "-pogAXtlHrDx",
            "--exclude", "/dev/",
            "--exclude", "/proc/",
            "--exclude", "/tmp/*",
            "--exclude", "/sys/",
            "--exclude", "/run/",
            "--exclude", "/boot/*rescue*",
            "--exclude", "/boot/loader/",
            "--exclude", "/boot/efi/loader/",
            "--exclude", "/etc/machine-id",
            self._mount_point,
            self._sysroot
        ]

        try:
            rc = execWithRedirect(cmd, args)
        except (OSError, RuntimeError) as e:
            msg = "Failed to install image: {}".format(e)
            raise PayloadInstallationError(msg) from None

        if rc == 11:
            raise PayloadInstallationError(
                "Failed to install image: "
                "{} exited with code {}".format(cmd, rc)
            )
