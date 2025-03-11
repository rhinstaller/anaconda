#
# DBus interface for the snapshot module.
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
from dasbus.server.interface import dbus_interface
from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.modules.common.base import KickstartModuleInterfaceTemplate
from pyanaconda.modules.common.constants.objects import SNAPSHOT
from pyanaconda.modules.common.containers import TaskContainer


@dbus_interface(SNAPSHOT.interface_name)
class SnapshotInterface(KickstartModuleInterfaceTemplate):
    """DBus interface for the snapshot module."""

    def IsRequested(self, when: Int) -> Bool:
        """Are there requests for snapshots of the given type?

        Types of the requests:
            0  Post-installation snapshots.
            1  Pre-installation snapshots.

        :param when: a type of the requests
        :return: True or False
        """
        return self.implementation.is_requested(when)

    def CreateWithTask(self, when: Int) -> ObjPath:
        """Create ThinLV snapshots.

        Types of the snapshots:
            0  Post-installation snapshots.
            1  Pre-installation snapshots.

        :param when: a type of the requests
        :return: a DBus path to a task
        """
        return TaskContainer.to_object_path(
            self.implementation.create_with_task(when)
        )
