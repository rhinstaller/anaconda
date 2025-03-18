#
# DBus interface for the NVDIMM module.
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
from pyanaconda.modules.common.constants.objects import NVDIMM
from pyanaconda.modules.common.containers import TaskContainer


@dbus_interface(NVDIMM.interface_name)
class NVDIMMInterface(KickstartModuleInterfaceTemplate):
    """DBus interface for the NVDIMM module."""

    def IsSupported(self) -> Bool:
        """Is this module supported?"""
        return self.implementation.is_supported()

    def GetDevicesToIgnore(self) -> List[Str]:
        """Get devices to be ignored.

        :return: a list of device names
        """
        return list(self.implementation.get_devices_to_ignore())

    def SetNamespacesToUse(self, namespaces: List[Str]):
        """Set namespaces to use.

        :param namespaces:  a list of namespaces
        """
        self.implementation.set_namespaces_to_use(namespaces)

    def ReconfigureWithTask(self, namespace: Str, mode: Str, sector_size: Int) -> ObjPath:
        """Reconfigure a namespace.

        :param namespace: a device name of a namespace (e.g. 'namespace0.0')
        :param mode: a new mode (one of 'sector', 'memory', 'dax')
        :param sector_size: a sector size for the sector mode
        :return: a DBus path to a task
        """
        return TaskContainer.to_object_path(
            self.implementation.reconfigure_with_task(namespace, mode, sector_size)
        )
