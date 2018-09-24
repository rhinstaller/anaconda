#
# Copyright (C) 2018 Red Hat, Inc.
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
import os

from pyanaconda.modules.common.task import Task
from pyanaconda.modules.subscription import system_purpose

class SystemPurposeConfigurationTask(Task):
    """Installation task for setting system purpose."""

    def __init__(self, sysroot, role, sla, usage, addons):
        """Create a new task.

        :param sysroot: a path to the root of the installed system
        :param lang: a value for LANG locale variable
        """
        super().__init__()
        self._sysroot = sysroot
        self._role = role
        self._sla = sla
        self._usage = usage
        self._addons = addons

    @property
    def name(self):
        return "Set system purpose"

    def run(self):
        system_purpose.give_the_system_purpose(self._sysroot,
                                                 self._role,
                                                 self._sla,
                                                 self._usage,
                                                 self._addons)
