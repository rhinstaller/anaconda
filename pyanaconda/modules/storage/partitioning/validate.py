#
# Tasks for the validation of the storage model.
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
from pyanaconda.modules.common.errors.storage import InvalidStorageError
from pyanaconda.modules.common.task.task import Task
from pyanaconda.storage.checker import storage_checker

__all__ = ["StorageValidateTask"]


class StorageValidateTask(Task):
    """A task for validating a storage model."""

    def __init__(self, storage):
        """Create a task.

        :param storage: an instance of Blivet
        """
        super().__init__()
        self._storage = storage

    @property
    def name(self):
        """Name of this task."""
        return "Validate a storage model"

    def run(self):
        """Run the validation."""
        self._validate_storage(self._storage)

    def _validate_storage(self, storage):
        """Validate the storage model.

        :param storage: an instance of Blivet
        :raises: InvalidStorageError if the model is not valid
        """
        report = storage_checker.check(storage)

        if not report.success:
            raise InvalidStorageError(" ".join(report.all_errors))
