#
# Copyright (C) 2024 Red Hat, Inc.
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
from pykickstart.constants import KS_SCRIPT_POST

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.modules.common.errors.runtime import ScriptError
from pyanaconda.modules.common.task import Task

log = get_module_logger(__name__)


class RunScriptsTask(Task):
    """Task for running scripts."""

    def __init__(self, script_type, scripts):
        """Create a new task.

        :param script_type: type of scripts to be run
        :type script_type: int
        :param scripts: list of scripts
        :type scripts: list(Script)
        """
        super().__init__()
        self._script_type = script_type
        self._scripts = scripts

    @property
    def name(self):
        return "Run scripts"

    def run(self):
        """Execute the task."""
        for script in self._scripts:
            if script.type == self._script_type:
                if script.type == KS_SCRIPT_POST:
                    result = script.run(conf.target.system_root)
                else:
                    result = script.run("/")
                if result:
                    lineno, err = result
                    error_message = f"{lineno}\n\n{err.strip()}"
                    raise ScriptError(error_message)
