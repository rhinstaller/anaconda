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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): David Lehman <dlehman@redhat.com>
#
import os
from blivet.size import Size
from pyanaconda import iutil

from pyanaconda.i18n import _, N_

import logging
log = logging.getLogger("anaconda")

class FileSystemSpaceChecker(object):
    """This object provides for a way to verify that enough space is available
       on configured file systems to support the current software selections.
       It is run as part of completeness checking every time a spoke changes,
       therefore moving this step up out of both the storage and software
       spokes.
    """
    error_template = N_("Not enough space in file systems for the current "
                        "software selection. An additional %s is needed.")

    def __init__(self, storage, payload):
        """Create a new FileSystemSpaceChecker object.

           Attributes:

           payload  -- An instance of a packaging.Payload subclass.
           storage  -- An instance of storage.Storage.
        """
        self.payload = payload
        self.storage = storage

        self.reset()

    def reset(self):
        """Get rid of any existing error messages and prepare to run the
           check again.
        """
        self.success = False
        self.deficit = Size(0)
        self.error_message = ""

    def check(self):
        """Check configured storage against software selections.  When this
           method is complete (which should be pretty quickly), the following
           attributes are available for inspection:

           success       -- A simple boolean defining whether there's enough
                            space or not.
           deficit       -- If unsuccessful, how much space the system is
                            short for current software selections.
           error_message -- If unsuccessful, an error message describing the
                            situation.  This message is suitable for putting
                            in the info bar at the bottom of a Hub.
        """
        self.reset()
        free = Size(self.storage.file_system_free_space)
        needed = self.payload.spaceRequired
        log.info("fs space: %s  needed: %s", free, needed)
        self.success = (free > needed)
        if not self.success:
            dev_required_size = self.payload.requiredDeviceSize(self.storage.root_device.format)
            self.deficit = dev_required_size - self.storage.root_device.size
            self.error_message = _(self.error_template) % self.deficit

        return self.success

class DirInstallSpaceChecker(FileSystemSpaceChecker):
    """Use the amount of space available at ROOT_PATH to calculate free space.

    This is used for the --dirinstall option where no storage is mounted and it
    is using space from the host's filesystem.
    """
    def check(self):
        """Check configured storage against software selections.  When this
           method is complete (which should be pretty quickly), the following
           attributes are available for inspection:

           success       -- A simple boolean defining whether there's enough
                            space or not.
           deficit       -- If unsuccessful, how much space the system is
                            short for current software selections.
           error_message -- If unsuccessful, an error message describing the
                            situation.  This message is suitable for putting
                            in the info bar at the bottom of a Hub.
        """
        self.reset()
        stat = os.statvfs(iutil.getSysroot())
        free = Size(stat.f_bsize * stat.f_bfree)
        needed = self.payload.spaceRequired
        log.info("fs space: %s  needed: %s", free, needed)
        self.success = (free > needed)
        if not self.success:
            dev_required_size = self.payload.requiredDeviceSize(self.storage.root_device.format)
            self.deficit = dev_required_size - self.storage.root_device.size
            self.error_message = _(self.error_template) % self.deficit

        return self.success
