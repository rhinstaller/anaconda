#
# DBus interface for the storage.
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
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.modules.common.base import KickstartModuleInterface
from pyanaconda.dbus.interface import dbus_interface
from pyanaconda.dbus.typing import *  # pylint: disable=wildcard-import


@dbus_interface(STORAGE.interface_name)
class StorageInterface(KickstartModuleInterface):
    """DBus interface for Storage module."""

    def ResetWithTask(self) -> ObjPath:
        """Reset the storage model.

        :return: a path to a task
        """
        return self.implementation.reset_with_task()
