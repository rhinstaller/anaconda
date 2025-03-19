#
# Copyright (C) 2022  Red Hat, Inc.
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
from pyanaconda.modules.common.task import Task

__all__ = ["ResetDNFManagerTask"]


class ResetDNFManagerTask(Task):
    """The task for resetting the DNF manager."""

    def __init__(self, dnf_manager):
        """Create a new task.

        :param dnf_manager: a DNF manager
        """
        super().__init__()
        self._dnf_manager = dnf_manager

    @property
    def name(self):
        return "Reset the DNF manager"

    def run(self):
        """Run the task.

        The reset will close all data sources used by the current DNF base.
        """
        self._dnf_manager.reset_base()
