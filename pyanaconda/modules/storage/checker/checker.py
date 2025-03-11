#
# The storage checker module
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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from blivet.size import Size

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.constants import STORAGE_MIN_RAM, STORAGE_SWAP_IS_RECOMMENDED
from pyanaconda.core.dbus import DBus
from pyanaconda.modules.common.base import KickstartBaseModule
from pyanaconda.modules.common.constants.objects import STORAGE_CHECKER
from pyanaconda.modules.common.errors.general import UnsupportedValueError
from pyanaconda.modules.storage.checker.checker_interface import StorageCheckerInterface
from pyanaconda.modules.storage.checker.utils import storage_checker

log = get_module_logger(__name__)

__all__ = ["StorageCheckerModule"]


class StorageCheckerModule(KickstartBaseModule):
    """The storage checker module."""

    def publish(self):
        """Publish the module."""
        DBus.publish_object(STORAGE_CHECKER.object_path, StorageCheckerInterface(self))

    def set_constraint(self, name, value):
        """Set a constraint to a new value.

        Supported constraints:

            min_ram  Minimal size of the total memory in bytes.
            swap_is_recommended  Recommend to specify a swap partition.

        :param str name: a name of the existing constraint
        :param value: a value of the constraint
        :raise: UnsupportedValueError if the constraint is not supported
        """
        if name == STORAGE_MIN_RAM:
            storage_checker.set_constraint(name, Size(value))
        elif name == STORAGE_SWAP_IS_RECOMMENDED:
            storage_checker.set_constraint(name, value)
        else:
            raise UnsupportedValueError(
                "Constraint '{}' is not supported.".format(name)
            )

        log.debug("Constraint '%s' is set to '%s'.", name, value)

    def process_kickstart(self, data):
        """Process the kickstart data."""
        if data.autopart.noswap:
            # Don't recommend swap if it is disabled for partitioning.
            self.set_constraint(STORAGE_SWAP_IS_RECOMMENDED, False)
