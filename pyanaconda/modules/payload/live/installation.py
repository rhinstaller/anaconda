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
from pyanaconda.modules.common.task import Task
from pyanaconda.modules.common.errors.payload import InstallError
from pyanaconda.core.constants import INSTALL_TREE
from pyanaconda.core.util import execWithRedirect
from pyanaconda.modules.payload.live.utils import create_rescue_image

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class InstallFromImageTask(Task):
    """Task to install the payload from image."""

    def __init__(self, dest_path, kernel_version_list):
        """Create a new task.

        :param dest_path: installation destination root path
        :type dest_path: str
        :param kernel_version_list: list of kernel versions for rescue initrd images
                                    to be created
        :type krenel_version_list: list(str)
        """
        super().__init__()
        self._dest_path = dest_path
        self._kernel_version_list = kernel_version_list

    @property
    def name(self):
        return "Install the payload from image"

    def run(self):
        """Run installation of the payload from image."""
        cmd = "rsync"
        # preserve: permissions, owners, groups, ACL's, xattrs, times,
        #           symlinks, hardlinks
        # go recursively, include devices and special files, don't cross
        # file system boundaries
        args = ["-pogAXtlHrDx", "--exclude", "/dev/", "--exclude", "/proc/", "--exclude", "/tmp/*",
                "--exclude", "/sys/", "--exclude", "/run/", "--exclude", "/boot/*rescue*",
                "--exclude", "/boot/loader/", "--exclude", "/boot/efi/loader/",
                "--exclude", "/etc/machine-id", INSTALL_TREE + "/", self._dest_path]
        try:
            rc = execWithRedirect(cmd, args)
        except (OSError, RuntimeError) as e:
            msg = None
            err = str(e)
            log.error(err)
        else:
            err = None
            msg = "%s exited with code %d" % (cmd, rc)
            log.info(msg)

        if err or rc == 11:
            raise InstallError(err or msg)

        create_rescue_image(self._dest_path, self._kernel_version_list)


class InstallFromTarTask(Task):
    """Task to install the payload from tarball."""

    def __init__(self, tarfile_path, dest_path, kernel_version_list):
        super().__init__()
        self._tarfile_path = tarfile_path
        self._dest_path = dest_path
        self._kernel_version_list = kernel_version_list

    @property
    def name(self):
        return "Install the payload from a tarball"

    def run(self):
        """Run installation of the payload from a tarball."""
        cmd = "tar"
        # preserve: ACL's, xattrs, and SELinux context
        args = ["--numeric-owner", "--selinux", "--acls", "--xattrs", "--xattrs-include", "*",
                "--exclude", "dev/*", "--exclude", "proc/*", "--exclude", "tmp/*",
                "--exclude", "sys/*", "--exclude", "run/*", "--exclude", "boot/*rescue*",
                "--exclude", "boot/loader", "--exclude", "boot/efi/loader",
                "--exclude", "etc/machine-id", "-xaf", self._tarfile_path, "-C", self._dest_path]
        try:
            rc = execWithRedirect(cmd, args)
        except (OSError, RuntimeError) as e:
            msg = None
            err = str(e)
            log.error(err)
        else:
            err = None
            msg = "%s exited with code %d" % (cmd, rc)
            log.info(msg)

        if err:
            raise InstallError(err or msg)

        create_rescue_image(self._dest_path, self._kernel_version_list)
