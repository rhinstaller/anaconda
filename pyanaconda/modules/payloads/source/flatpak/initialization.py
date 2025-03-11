#
# Copyright (C) 2021  Red Hat, Inc.
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
from blivet.size import Size

from pyanaconda.modules.common.task import Task
from pyanaconda.modules.payloads.payload.rpm_ostree.flatpak_manager import (
    FlatpakManager,
)

__all__ = ["GetFlatpaksSizeTask"]


class GetFlatpaksSizeTask(Task):
    """Task to find size of flatpaks from the local source on Silverblue."""

    def __init__(self, sysroot):
        """Create a new task.

        :param str sysroot: path to the system root
        """
        super().__init__()
        self._sysroot = sysroot

    @property
    def name(self):
        return "Find size of flatpaks"

    def run(self):
        """Find the size of flatpaks to install.

        :return: the required size in bytes
        :rtype: int
        """
        flatpak_payload = FlatpakManager(self._sysroot)

        try:
            # Initialize temporal repo to enable reading of the remote
            flatpak_payload.initialize_with_path("/var/tmp/anaconda-flatpak-temp")

            # Return the size in bytes.
            required_size = Size(flatpak_payload.get_required_size())
            return required_size.get_bytes()

        finally:
            # Clean up temporal repo again
            flatpak_payload.cleanup()
