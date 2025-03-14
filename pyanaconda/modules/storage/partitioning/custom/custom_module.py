#
# Custom partitioning module.
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
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.modules.common.errors.storage import UnavailableDataError
from pyanaconda.modules.storage.partitioning.base import PartitioningModule
from pyanaconda.modules.storage.partitioning.constants import PartitioningMethod
from pyanaconda.modules.storage.partitioning.custom.custom_interface import (
    CustomPartitioningInterface,
)
from pyanaconda.modules.storage.partitioning.custom.custom_partitioning import (
    CustomPartitioningTask,
)

log = get_module_logger(__name__)


class CustomPartitioningModule(PartitioningModule):
    """The custom partitioning module."""

    def __init__(self):
        """Initialize the module."""
        super().__init__()
        self._data = None

    @property
    def partitioning_method(self):
        """Type of the partitioning method."""
        return PartitioningMethod.CUSTOM

    @property
    def data(self):
        """The partitioning data.

        :return: an instance of kickstart data
        """
        if self._data is None:
            raise UnavailableDataError()

        return self._data

    def for_publication(self):
        """Return a DBus representation."""
        return CustomPartitioningInterface(self)

    def process_kickstart(self, data):
        """Process the kickstart data."""
        # FIXME: Don't keep everything.
        self._data = data

        # FIXME: Remove this ugly hack.
        self._data.onPart = {}

    def requires_passphrase(self):
        """Is the default passphrase required?

        :return: True or False
        """
        return bool(self._find_data_without_passphrase())

    def set_passphrase(self, passphrase):
        """Set a default passphrase for all encrypted devices.

        :param passphrase: a string with a passphrase
        """
        self._set_data_without_passphrase(passphrase)

    def _find_data_without_passphrase(self):
        """Collect kickstart data that require a passphrase.

        :return: a list of kickstart data objects
        """
        data_list = \
            self.data.partition.dataList() + \
            self.data.logvol.dataList() + \
            self.data.raid.dataList()

        return [data for data in data_list if data.encrypted and not data.passphrase]

    def _set_data_without_passphrase(self, passphrase):
        """Set up kickstart data that require a passphrase.

        :param passphrase: a passphrase
        """
        for data in self._find_data_without_passphrase():
            data.passphrase = passphrase

    def configure_with_task(self):
        """Schedule the partitioning actions."""
        return CustomPartitioningTask(self.storage, self.data)
