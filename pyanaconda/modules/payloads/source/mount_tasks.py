#
# Base object for payload sources that use mounting.
#
# Copyright (C) 2020 Red Hat, Inc.
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
import os.path
from abc import ABC, abstractmethod

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.modules.common.errors.payload import (
    SourceSetupError,
    SourceTearDownError,
)
from pyanaconda.modules.common.task import Task
from pyanaconda.payload.utils import unmount

log = get_module_logger(__name__)


class TearDownMountTask(Task):
    """Task to tear down a mounting installation source.

    This is universal for any source that can be directly unmounted with no additional work.
    """

    def __init__(self, target_mount):
        super().__init__()
        self._target_mount = target_mount

    @property
    def name(self):
        return "Unmount an installation source"

    def run(self):
        """Run source un-setup."""
        log.debug("Unmounting installation source")
        self._do_unmount()
        self._check_mount()

    def _do_unmount(self):
        """Unmount the source."""
        unmount(self._target_mount)

    def _check_mount(self):
        """Check if the source is unmounted."""
        if os.path.ismount(self._target_mount):
            raise SourceTearDownError("The mount point {} is still in use.".format(
                self._target_mount
            ))


class SetUpMountTask(Task, ABC):
    """Abstract base class for set up tasks that need mounting."""

    def __init__(self, target_mount):
        super().__init__()
        self._target_mount = target_mount

    def run(self):
        """Run source setup."""
        log.debug("Mounting installation source")
        self._check_mount()
        return self._do_mount()

    def _check_mount(self):
        """Check if the source is unmounted."""
        if os.path.ismount(self._target_mount):
            raise SourceSetupError("The mount point {} is already in use.".format(
                self._target_mount
            ))

    @abstractmethod
    def _do_mount(self):
        """Mount the source.

        Override this method in descendants to do the actual work of mounting.
        Return the result you want returned from the task.
        """
        pass
