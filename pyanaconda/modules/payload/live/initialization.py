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
import os
import glob

from pyanaconda.modules.common.task import Task
from pyanaconda.core.util import execWithRedirect

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class UpdateBLSConfigurationTask(Task):
    """Task to update BLS configuration."""

    def __init__(self, sysroot, kernel_version_list):
        """Create a new task.

        :param sysroot: a path to the root of the installed system
        :type sysroot: str
        :param kernel_version_list: list of kernel versions for updating of BLS configuration
        :type krenel_version_list: list(str)
        """
        super().__init__()
        self._sysroot = sysroot
        self._kernel_version_list = kernel_version_list

    @property
    def name(self):
        return "Update BLS configuration."""

    def run(self):
        """Run update of bls configuration."""
        # Not using BLS configuration, skip it
        if os.path.exists(self._sysroot + "/usr/sbin/new-kernel-pkg"):
            return

        # TODO: test if this is not a dir install

        # Remove any existing BLS entries, they will not match the new system's
        # machine-id or /boot mountpoint.
        for file in glob.glob(self._sysroot + "/boot/loader/entries/*.conf"):
            log.info("Removing old BLS entry: %s", file)
            os.unlink(file)

        # Create new BLS entries for this system
        for kernel in self._kernel_version_list:
            log.info("Regenerating BLS info for %s", kernel)
            execWithRedirect(
                "kernel-install",
                ["add", kernel, "/lib/modules/{0}/vmlinuz".format(kernel)],
                root=self._sysroot
            )
