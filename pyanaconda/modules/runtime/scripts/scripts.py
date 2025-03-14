#
# The user interface module
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
# Set up the modules logger.
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.dbus import DBus
from pyanaconda.modules.common.base import KickstartBaseModule
from pyanaconda.modules.common.constants.objects import SCRIPTS
from pyanaconda.modules.runtime.scripts.runtime import RunScriptsTask
from pyanaconda.modules.runtime.scripts.scripts_interface import ScriptsInterface

log = get_module_logger(__name__)

__all__ = ["ScriptsModule"]


class ScriptsModule(KickstartBaseModule):
    def __init__(self):
        super().__init__()
        self._scripts = []

    def publish(self):
        """Publish the module."""
        DBus.publish_object(SCRIPTS.object_path, ScriptsInterface(self))

    def process_kickstart(self, data):
        log.debug("Process_kickstart %s", data.scripts)
        self._scripts = data.scripts

    def setup_kickstart(self, data):
        log.debug("Setup_kickstart %s", data)
        data.scripts = self._scripts

    def run_scripts_with_task(self, script_type):
        """Run all scripts of given type sequentially."""
        log.debug("Running %s scripts with task", script_type)
        return RunScriptsTask(
            script_type=script_type,
            scripts=self._scripts
        )
