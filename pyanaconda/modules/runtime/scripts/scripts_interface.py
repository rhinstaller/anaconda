#
# DBus interface for the scripts module
#
# Copyright (C) 2021 Red Hat, Inc.
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
from dasbus.server.interface import dbus_interface
from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.modules.common.base import KickstartModuleInterfaceTemplate
from pyanaconda.modules.common.constants.objects import SCRIPTS
from pyanaconda.modules.common.containers import TaskContainer

__all__ = ["ScriptsInterface"]


@dbus_interface(SCRIPTS.interface_name)
class ScriptsInterface(KickstartModuleInterfaceTemplate):
    """DBus interface for the scripts module."""

    def RunScriptsWithTask(self, script_type: Int) -> ObjPath:
        """Run all scripts of given type sequentially with task.

        The types of scripts:
        kickstart scripts:
        KS_SCRIPT_PRE = 0
        KS_SCRIPT_POST = 1
        KS_SCRIPT_TRACEBACK = 2
        KS_SCRIPT_PREINSTALL = 3
        KS_SCRIPT_ONERROR = 4
        :param script_type: Type of scripts to be run.
        :return: a DBus path of the task
        """
        return TaskContainer.to_object_path(
            self.implementation.run_scripts_with_task(script_type)
        )
