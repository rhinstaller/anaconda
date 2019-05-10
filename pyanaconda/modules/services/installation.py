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

from pyanaconda.core import util

from pyanaconda.modules.common.task import Task
from pyanaconda.modules.services.constants import SetupOnBootAction

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

__all__ = ["ConfigureInitialSetupTask"]


class ConfigureInitialSetupTask(Task):
    """Installation task for Initial Setup configuration."""

    def __init__(self, sysroot, setup_on_boot):
        """Create a new root password configuration task.

        :param str sysroot: a path to the root of the target system
        :param enum setup_on_boot: setup-on-boot mode for Initial Setup

        Modes are defined by the SetupOnBoot enum as distinct integers.

        """
        super().__init__()
        self._sysroot = sysroot
        self._setup_on_boot = setup_on_boot

    @property
    def name(self):
        return "Configure Initial Setup"

    def run(self):
        unit_name = "initial-setup.service"
        if self._setup_on_boot == SetupOnBootAction.DISABLED:
            log.debug("Initial Setup will be disabled.")
            util.disable_service(unit_name)
            return

        if not os.path.exists(os.path.join(self._sysroot, "lib/systemd/system/", unit_name)):
            log.debug("Initial Setup will not be started on first boot, because "
                      "it's unit file (%s) is not installed.", unit_name)
            return

        if self._setup_on_boot == SetupOnBootAction.RECONFIG:
            log.debug("Initial Setup will run in reconfiguration mode.")
            # write the reconfig trigger file
            f = open(os.path.join(self._sysroot, "etc/reconfigSys"), "w+")
            f.close()

        log.debug("Initial Setup will be enabled.")
        util.enable_service(unit_name)
