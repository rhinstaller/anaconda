#
# DBus interface for a partitioning module.
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
from pyanaconda.modules.common.base.base_template import ModuleInterfaceTemplate
from pyanaconda.dbus.interface import dbus_interface
from pyanaconda.dbus.typing import *  # pylint: disable=wildcard-import
from pyanaconda.modules.common.constants.interfaces import PARTITIONING

__all__ = ["PartitioningInterface"]


@dbus_interface(PARTITIONING.interface_name)
class PartitioningInterface(ModuleInterfaceTemplate):
    """DBus interface for a partitioning module."""

    def ConfigureWithTask(self) -> ObjPath:
        """Schedule the partitioning actions.

        :return: a DBus path to a task
        """
        return self.implementation.configure_with_task()

    def ValidateWithTask(self) -> ObjPath:
        """Validate the scheduled partitioning.

        Run sanity checks on the current storage model to
        verify if the partitioning is valid.

        :return: a DBus path to a task
        """
        return self.implementation.validate_with_task()
