#
# Copyright (C) 2020  Red Hat, Inc.
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

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core import util
from pyanaconda.modules.common.task import Task

log = get_module_logger(__name__)


class ImportRPMKeysTask(Task):
    """The installation task for import of the RPM keys."""

    def __init__(self, sysroot, gpg_keys):
        """Create a new task.

        :param sysroot: a path to the system root
        :param gpg_keys: a list of gpg keys to import
        """
        super().__init__()
        self._sysroot = sysroot
        self._gpg_keys = gpg_keys

    @property
    def name(self):
        return "Import RPM keys"

    def run(self):
        """Run the task"""
        if not self._gpg_keys:
            log.debug("No GPG keys to import.")
            return

        if not os.path.exists(self._sysroot + "/usr/bin/rpm"):
            log.error(
                "Can not import GPG keys to RPM database because "
                "the 'rpm' executable is missing on the target "
                "system. The following keys were not imported:\n%s",
                "\n".join(self._gpg_keys)
            )
            return

        # Get substitutions for variables.
        # TODO: replace the interpolation with DNF once possible
        basearch = util.execWithCapture("uname", ["-i"]).strip().replace("'", "")
        releasever = util.get_os_release_value("VERSION_ID", sysroot=self._sysroot) or ""

        # Import GPG keys to RPM database.
        for key in self._gpg_keys:
            key = key.replace("$releasever", releasever).replace("$basearch", basearch)

            log.info("Importing GPG key to RPM database: %s", key)
            rc = util.execWithRedirect("rpm", ["--import", key], root=self._sysroot)

            if rc:
                log.error("Failed to import the GPG key.")
