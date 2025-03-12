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
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.path import make_directories
from pyanaconda.core.util import execWithRedirect
from pyanaconda.modules.common.errors.payload import SourceSetupError
from pyanaconda.modules.payloads.source.mount_tasks import SetUpMountTask

log = get_module_logger(__name__)

__all__ = ["SetUpHMCSourceTask"]


class SetUpHMCSourceTask(SetUpMountTask):
    """Task to set up the SE/HMC source."""

    @property
    def name(self):
        return "Set up the SE/HMC source"

    def _do_mount(self):
        """Set up the installation source."""
        log.debug("Trying to mount the content of HMC media drive.")

        # Test the SE/HMC file access.
        if execWithRedirect("/usr/sbin/lshmc", []):
            raise SourceSetupError("The content of HMC media drive couldn't be accessed.")

        # Make sure that the directories exists.
        make_directories(self._target_mount)

        # Mount the device.
        if execWithRedirect("/usr/bin/hmcdrvfs", [self._target_mount]):
            raise SourceSetupError("The content of HMC media drive couldn't be mounted.")

        log.debug("We are ready to use the HMC at %s.", self._target_mount)
