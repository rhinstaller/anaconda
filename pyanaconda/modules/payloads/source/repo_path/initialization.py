#
# Copyright (C) 2023 Red Hat, Inc.
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
from pyanaconda.modules.common.errors.payload import SourceSetupError
from pyanaconda.modules.common.task import Task
from pyanaconda.modules.payloads.source.utils import verify_valid_repository

log = get_module_logger(__name__)

__all__ = ["SetUpRepoPathSourceTask"]


class SetUpRepoPathSourceTask(Task):
    """Task to set up a local repo path."""

    def __init__(self, path):
        super().__init__()
        self._path = path

    @property
    def name(self):
        """Name of the task."""
        return "Set up a local path to a repository"

    def run(self):
        """Run the task."""
        log.debug("Trying to detect a repository at '%s'.", self._path)

        if not verify_valid_repository(self._path):
            raise SourceSetupError("Nothing useful found at '{}'".format(self._path))
