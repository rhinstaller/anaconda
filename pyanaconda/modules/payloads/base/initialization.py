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
import traceback

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.modules.common.errors.payload import SourceSetupError, SourceTearDownError
from pyanaconda.modules.common.task import Task

log = get_module_logger(__name__)

__all__ = ["SetUpSourcesTask", "TearDownSourcesTask"]


class SetUpSourcesTask(Task):
    """Set up all the installation source of the payload."""

    def __init__(self, sources):
        """Create set up sources task.

        The task will group all the sources set up tasks under this one.

        :param sources: list of sources
        :type sources: [instance of PayloadSourceBase class]
        """
        super().__init__()
        self._sources = sources

    @property
    def name(self):
        return "Set Up Installation Sources"

    def run(self):
        """Collect and call set up tasks for all the sources."""
        if not self._sources:
            raise SourceSetupError("No sources specified for set up!")

        for source in self._sources:
            tasks = source.set_up_with_tasks()
            log.debug("Collected %s tasks from %s source",
                      [task.name for task in tasks],
                      source.type)

            for task in tasks:
                log.debug("Running task %s", task.name)
                task.run_with_signals()


class TearDownSourcesTask(Task):
    """Tear down all the installation sources of the payload."""

    def __init__(self, sources):
        """Create tear down sources task.

        The task will group all the sources tear down tasks under this one.

        :param sources: list of sources
        :type sources: [instance of PayloadSourceBase class]
        """
        super().__init__()
        self._sources = sources

    @property
    def name(self):
        return "Tear Down Installation Sources"

    def run(self):
        """Collect and call tear down tasks for all the sources."""
        if not self._sources:
            raise SourceSetupError("No sources specified for tear down!")

        errors = []

        for source in self._sources:
            tasks = source.tear_down_with_tasks()
            log.debug("Collected %s tasks from %s source",
                      [task.name for task in tasks],
                      source.type)

            for task in tasks:
                log.debug("Running task %s", task.name)
                try:
                    task.run()
                except SourceTearDownError as e:
                    message = "Task '{}' from source '{}' has failed, reason: {}".format(
                        task.name, source.type, str(e))
                    errors.append(message)
                    log.error("%s\n%s", message, traceback.format_exc())

        if errors:
            raise SourceTearDownError("Sources tear down have failed", errors)
