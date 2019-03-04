#
# Blivet partitioning module.
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
from blivetgui.osinstall import BlivetUtilsAnaconda

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.dbus import DBus
from pyanaconda.modules.common.constants.objects import BLIVET_PARTITIONING
from pyanaconda.modules.storage.partitioning.base import PartitioningModule
from pyanaconda.modules.storage.partitioning.blivet_interface import \
    BlivetPartitioningInterface
from pyanaconda.modules.storage.partitioning.configure import StorageConfigureTask
from pyanaconda.modules.storage.partitioning.validate import StorageValidateTask
from pyanaconda.storage.execution import InteractivePartitioningExecutor

log = get_module_logger(__name__)


class BlivetPartitioningModule(PartitioningModule):
    """The partitioning module for Blivet-GUI."""

    def __init__(self):
        super().__init__()
        self._handler = None

    def publish(self):
        """Publish the module."""
        DBus.publish_object(BLIVET_PARTITIONING.object_path, BlivetPartitioningInterface(self))

    @property
    def storage_handler(self):
        """The handler of the storage.

        :return: an instance of BlivetUtils
        """
        if not self._handler:
            self._handler = BlivetUtilsAnaconda()

        # Make sure that the handler always uses the current storage.
        self._handler.storage = self.storage
        return self._handler

    def configure_with_task(self):
        """Complete the scheduled partitioning."""
        task = StorageConfigureTask(self.storage, InteractivePartitioningExecutor())
        path = self.publish_task(BLIVET_PARTITIONING.namespace, task)
        return path

    def validate_with_task(self):
        """Validate the scheduled partitions."""
        task = StorageValidateTask(self.storage)
        path = self.publish_task(BLIVET_PARTITIONING.namespace, task)
        return path
