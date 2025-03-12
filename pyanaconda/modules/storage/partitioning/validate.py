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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.modules.common.structures.validation import ValidationReport
from pyanaconda.modules.common.task.task import ValidationTask
from pyanaconda.modules.storage.checker.utils import storage_checker

log = get_module_logger(__name__)

__all__ = ["StorageValidateTask"]


class StorageValidateTask(ValidationTask):
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
        """Run the validation.

        :return: a validation report
        """
        return self._validate_storage(self._storage)

    def _validate_storage(self, storage):
        """Validate the storage model.

        :param storage: an instance of Blivet
        :return: a validation report
        """
        result = storage_checker.check(storage)

        for message in result.info:
            log.debug(message)

        validation_report = ValidationReport()
        validation_report.error_messages = result.errors
        validation_report.warning_messages = result.warnings

        return validation_report
