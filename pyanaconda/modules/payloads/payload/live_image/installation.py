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
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.util import execWithRedirect
from pyanaconda.modules.common.errors.payload import InstallError
from pyanaconda.modules.common.task import Task

log = get_module_logger(__name__)


class InstallFromTarTask(Task):
    """Task to install the payload from tarball."""

    def __init__(self, tarfile_path, dest_path):
        super().__init__()
        self._tarfile_path = tarfile_path
        self._dest_path = dest_path

    @property
    def name(self):
        return "Install the payload from a tarball"

    def run(self):
        """Run installation of the payload from a tarball."""
        cmd = "tar"
        # preserve: ACL's, xattrs, and SELinux context
        args = ["--numeric-owner", "--selinux", "--acls", "--xattrs", "--xattrs-include", "*",
                "--exclude", "./dev/*", "--exclude", "./proc/*", "--exclude", "./tmp/*",
                "--exclude", "./sys/*", "--exclude", "./run/*", "--exclude", "./boot/*rescue*",
                "--exclude", "./boot/loader", "--exclude", "./boot/efi/loader",
                "--exclude", "./etc/machine-id", "--exclude", "./etc/machine-info",
                "-xaf", self._tarfile_path, "-C", self._dest_path]
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
