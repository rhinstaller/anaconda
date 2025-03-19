#
# Copyright (C) 2023 Red Hat, Inc.
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
import os
import shutil

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.path import join_paths, make_directories
from pyanaconda.modules.common.task import Task

log = get_module_logger(__name__)


class CopyTransientGnomeInitialSetupStateTask(Task):
    """Task to copy transient gnome-initial-setup configuration from live system to installed system"""

    def __init__(self, sysroot):
        """Create a new task."""
        super().__init__()
        self._sysroot = sysroot
        self._paths = ['/var/lib/gnome-initial-setup/state']

    @property
    def name(self):
        """Name of the task."""
        return "Transfer transient gnome-initial-setup live system configuration to installed system"""

    def run(self):
        """Run the task."""
        for path in self._paths:
            destination_path = join_paths(self._sysroot, path.lstrip('/'))
            destination_dir = os.path.dirname(destination_path)
            make_directories(destination_dir)
            log.debug("Copying %s to %s", path, destination_path)
            if os.path.exists(path):
                shutil.copy2(path, destination_path)
