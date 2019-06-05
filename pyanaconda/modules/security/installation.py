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

from pyanaconda.simpleconfig import SimpleConfigFile

from pyanaconda.modules.common.task import Task
from pyanaconda.modules.security.constants import SELinuxMode

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

__all__ = ["ConfigureSELinuxTask"]


class ConfigureSELinuxTask(Task):
    """Installation task for Initial Setup configuration."""

    SELINUX_CONFIG_PATH = "etc/selinux/config"

    SELINUX_STATES = {
        SELinuxMode.DISABLED: "disabled",
        SELinuxMode.ENFORCING: "enforcing",
        SELinuxMode.PERMISSIVE: "permissive"
    }

    def __init__(self, sysroot, selinux_mode):
        """Create a new Initial Setup configuration task.

        :param str sysroot: a path to the root of the target system
        :param int selinux_mode: SELinux mode id

        States are defined by the SELinuxMode enum as distinct integers.
        """
        super().__init__()
        self._sysroot = sysroot
        self._selinux_mode = selinux_mode

    @property
    def name(self):
        return "Configure SELinux"


    def run(self):
        if self._selinux_mode == SELinuxMode.DEFAULT:
            log.debug("Use SELinux default configuration.")
            return

        if self._selinux_mode not in self.SELINUX_STATES:
            log.error("Unknown SELinux state for %s.", self._selinux_mode)
            return

        try:
            selinux_cfg = SimpleConfigFile(os.path.join(self._sysroot, self.SELINUX_CONFIG_PATH))
            selinux_cfg.read()
            selinux_cfg.set(("SELINUX", self.SELINUX_STATES[self._selinux_mode]))
            selinux_cfg.write()
        except IOError as msg:
            log.error("SELinux configuration failed: %s", msg)
