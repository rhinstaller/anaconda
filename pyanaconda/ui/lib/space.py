# User interface library functions for filesystem/disk space checking
#
# Copyright (C) 2012  Red Hat, Inc.
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

from blivet.size import Size

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.i18n import _
from pyanaconda.modules.common.constants.objects import DEVICE_TREE
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.modules.common.structures.storage import DeviceData

log = get_module_logger(__name__)


class FileSystemSpaceChecker:
    """This object provides for a way to verify that enough space is available
       on configured file systems to support the current software selections.
       It is run as part of completeness checking every time a spoke changes,
       therefore moving this step up out of both the storage and software
       spokes.
    """
    def __init__(self, payload):
        """Create a new FileSystemSpaceChecker object.

           Attributes:

           payload  -- An instance of a payload.Payload subclass.
           storage  -- An instance of storage.Storage.
        """
        self.payload = payload
        self.device_tree = STORAGE.get_proxy(DEVICE_TREE)
        self.success = False
        self.error_message = ""

    def _calculate_free_space(self):
        """Calculate the available space."""
        return Size(self.device_tree.GetFreeSpaceForSystem(("/", "/usr")))

    def _calculate_needed_space(self):
        """Calculate the needed space."""
        return self.payload.space_required

    def _calculate_deficit(self, needed):
        """Calculate the deficit.

        Return None if the deficit cannot be calculated.

        :param needed: a needed space
        :return: a deficit size or None
        """
        root_id = self.device_tree.GetRootDevice()

        if not root_id:
            return None

        root_data = DeviceData.from_structure(
            self.device_tree.GetDeviceData(root_id)
        )

        current = root_data.size
        required = self.device_tree.GetRequiredDeviceSize(needed.get_bytes())
        return Size(required - current)

    def check(self):
        """Check configured storage against software selections.  When this
           method is complete (which should be pretty quickly), the following
           attributes are available for inspection:

           success       -- A simple boolean defining whether there's enough
                            space or not.
           error_message -- If unsuccessful, an error message describing the
                            situation.  This message is suitable for putting
                            in the info bar at the bottom of a Hub.
        """
        free = self._calculate_free_space()
        needed = self._calculate_needed_space()
        log.info("fs space: %s  needed: %s", free, needed)

        if free > needed:
            result = True
            message = ""
        else:
            result = False
            deficit = self._calculate_deficit(needed)

            if deficit:
                message = _("Not enough space in file systems for the current software selection. "
                            "An additional {} is needed.").format(deficit)
            else:
                message = _("Not enough space in file systems for the current software selection.")

        self.success = result
        self.error_message = message
        return result


class DirInstallSpaceChecker(FileSystemSpaceChecker):
    """Use the amount of space available at ROOT_PATH to calculate free space.

    This is used for the --dirinstall option where no storage is mounted and it
    is using space from the host's filesystem.
    """

    def _calculate_free_space(self):
        """Calculate the available space."""
        stat = os.statvfs(conf.target.physical_root)
        return Size(stat.f_bsize * stat.f_bfree)

    def _calculate_deficit(self, needed):
        """Calculate the deficit."""
        return None
