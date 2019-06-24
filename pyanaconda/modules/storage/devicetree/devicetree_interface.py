#
# DBus interface for the device tree module
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

from pyanaconda.dbus.interface import dbus_class
from pyanaconda.dbus.namespace import get_dbus_path
from pyanaconda.modules.storage.devicetree.handler_interface import DeviceTreeHandlerInterface
from pyanaconda.modules.storage.devicetree.viewer_interface import DeviceTreeViewerInterface

__all__ = ["DeviceTreeInterface"]


@dbus_class
class DeviceTreeInterface(DeviceTreeViewerInterface, DeviceTreeHandlerInterface):
    """DBus interface for the device tree module."""

    _tree_counter = 1

    @staticmethod
    def get_object_path(namespace):
        """Get the unique object path in the given namespace.

        This method is not thread safe for now.

        :param namespace: a sequence of names
        :return: a DBus path of a device tree
        """
        tree_number = DeviceTreeInterface._tree_counter
        DeviceTreeInterface._tree_counter += 1
        return get_dbus_path(*namespace, "DeviceTree", str(tree_number))
