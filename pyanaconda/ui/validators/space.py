# The class for the filesystem/disk space validation.
#
# Copyright (C) 2016  Red Hat, Inc.
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
# Author(s):  Vendula Poncova <vponcova@redhat.com>
#
import logging

from pyanaconda.flags import flags
from pyanaconda.i18n import N_, _
from pyanaconda.ui.lib.space import FileSystemSpaceChecker, DirInstallSpaceChecker
from pyanaconda.ui.validators import BaseValidator
from pyanaconda.ui.validators.software import SoftwareValidator
from pyanaconda.ui.validators.storage import StorageValidator

log = logging.getLogger("anaconda")

__all__ = ["SpaceValidator"]


class SpaceValidator(BaseValidator):
    """A class to check if there is enough space in file systems."""

    title = N_("Space validation")
    depends_on = [SoftwareValidator, StorageValidator]

    def __init__(self, config):
        super(SpaceValidator, self).__init__(config)
        self._storage = config.storage
        self._payload = config.payload

        # Setup the space checker.
        if not flags.dirInstall:
            self._checker = FileSystemSpaceChecker(self._storage, self._payload)
        else:
            self._checker = DirInstallSpaceChecker(self._storage, self._payload)

    def _is_valid(self):
        return self._storage.root_device and self._checker.check()

    def _get_validation_error(self):
        if not self._storage.root_device:
            return _("The storage is not set up.")
        else:
            return self._checker.error_message


