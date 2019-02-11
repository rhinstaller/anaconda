#
# The module for partitioning.
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
from abc import abstractmethod

from pyanaconda.modules.common.base.base import KickstartBaseModule
from pyanaconda.modules.common.errors.storage import UnavailableStorageError
from pyanaconda.anaconda_loggers import get_module_logger

log = get_module_logger(__name__)

__all__ = ["PartitioningModule"]


class PartitioningModule(KickstartBaseModule):
    """The partitioning module."""

    def __init__(self):
        """Create the module."""
        super().__init__()
        self._current_storage = None
        self._storage_playground = None

    @property
    def storage(self):
        """The storage model.

        Provides a copy of the current storage model,
        that can be safely used for partitioning.

        :return: an instance of Blivet
        """
        if self._current_storage is None:
            raise UnavailableStorageError()

        if self._storage_playground is None:
            self._storage_playground = self._current_storage.copy()

        return self._storage_playground

    def on_storage_reset(self, storage):
        """Keep the instance of the current storage."""
        self._current_storage = storage

    @abstractmethod
    def configure_with_task(self):
        """Schedule the partitioning actions.

        :return: a DBus path to a task
        """
        pass

    @abstractmethod
    def validate_with_task(self):
        """Validate the scheduled partitioning.

        Run sanity checks on the current storage model to
        verify if the partitioning is valid.

        :return: a DBus path to a task
        """
        pass
