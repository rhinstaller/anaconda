#
# The device tree module
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
from dasbus.server.publishable import Publishable

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.dbus import DBus
from pyanaconda.modules.common.constants.objects import DEVICE_TREE
from pyanaconda.modules.storage.devicetree.devicetree_interface import (
    DeviceTreeInterface,
)
from pyanaconda.modules.storage.devicetree.handler import DeviceTreeHandler
from pyanaconda.modules.storage.devicetree.viewer import DeviceTreeViewer
from pyanaconda.modules.storage.storage_subscriber import StorageSubscriberModule

log = get_module_logger(__name__)

__all__ = ["DeviceTreeModule"]


class DeviceTreeModule(StorageSubscriberModule, DeviceTreeViewer, DeviceTreeHandler, Publishable):
    """The device tree module."""

    def for_publication(self):
        """Return a DBus representation."""
        return DeviceTreeInterface(self)

    def publish(self):
        """Publish the module."""
        DBus.publish_object(DEVICE_TREE.object_path, self.for_publication())
