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
import glob

from pyanaconda.core.util import join_paths
from pyanaconda.modules.common.errors.payload import SourceSetupError
from pyanaconda.modules.common.task import Task

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

__all__ = ["SetUpRepoFilesSourceTask"]


class SetUpRepoFilesSourceTask(Task):
    """Task to setup installation source."""

    def __init__(self, repo_dirs):
        super().__init__()
        self._repo_dirs = repo_dirs

    @property
    def name(self):
        return "Set up Repo files Installation Source"

    def run(self):
        """Run Repo files installation source setup."""
        log.debug("Trying to detect repo files automatically")
        for repo_dir in self._repo_dirs:
            if len(glob.glob(join_paths(repo_dir, "*.repo"))) > 0:
                return
        raise SourceSetupError("repo files not found")
