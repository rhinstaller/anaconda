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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.dbus import DBus
from pyanaconda.modules.common.constants.objects import CUSTOM_PARTITIONING
from pyanaconda.modules.common.errors.storage import UnavailableDataError
from pyanaconda.modules.storage.partitioning.base import PartitioningModule
from pyanaconda.modules.storage.partitioning.custom_interface import CustomPartitioningInterface
from pyanaconda.modules.storage.partitioning.custom_partitioning import CustomPartitioningTask
from pyanaconda.modules.storage.partitioning.validate import StorageValidateTask

log = get_module_logger(__name__)


class CustomPartitioningModule(PartitioningModule):
    """The custom partitioning module."""

    def __init__(self):
        """Initialize the module."""
        super().__init__()
        self._data = None

    @property
    def data(self):
        """The partitioning data.

        :return: an instance of kickstart data
        """
        if self._data is None:
            raise UnavailableDataError()

        return self._data

    def publish(self):
        """Publish the module."""
        DBus.publish_object(CUSTOM_PARTITIONING.object_path, CustomPartitioningInterface(self))

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
        task = CustomPartitioningTask(self.storage, self.data)
        path = self.publish_task(CUSTOM_PARTITIONING.namespace, task)
        return path

    def validate_with_task(self):
        """Validate the scheduled partitions."""
        task = StorageValidateTask(self.storage)
        path = self.publish_task(CUSTOM_PARTITIONING.namespace, task)
        return path
