#
# NVDIMM module
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
import gi
gi.require_version("BlockDev", "2.0")
from gi.repository import BlockDev as blockdev

from blivet.static_data import nvdimm

from pykickstart.constants import NVDIMM_ACTION_RECONFIGURE, NVDIMM_ACTION_USE

from pyanaconda.dbus import DBus
from pyanaconda.modules.common.base import KickstartBaseModule
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.modules.common.constants.objects import NVDIMM
from pyanaconda.modules.storage.nvdimm.nvdimm_interface import NVDIMMInterface

log = get_module_logger(__name__)

__all__ = ["NVDIMMModule"]


class NVDIMMModule(KickstartBaseModule):
    """The NVDIMM module."""

    def __init__(self):
        super().__init__()
        self._actions = list()

    def publish(self):
        """Publish the module."""
        DBus.publish_object(NVDIMM.object_path, NVDIMMInterface(self))

    def process_kickstart(self, data):
        """Process the kickstart data."""
        self._actions = data.nvdimm.actionList

    def setup_kickstart(self, data):
        """Setup the kickstart data."""
        data.nvdimm.actionList = self._actions

    def get_namespaces_to_use(self):
        """Get namespaces to be used.

        FIXME: Can we return an empty string in the set?

        :return: a set of namespaces
        """
        return {
            action.namespace for action in self._actions
            if action.action == NVDIMM_ACTION_RECONFIGURE
            or (action.action == NVDIMM_ACTION_USE and action.namespace)
        }

    def get_devices_to_use(self):
        """Get devices to be used.

        :return: a set to device names
        """
        return {
            dev for action in self._actions for dev in action.blockdevs
            if action.action == NVDIMM_ACTION_USE and action.blockdevs
        }

    def get_devices_to_ignore(self):
        """Get devices to be ignored.

        By default nvdimm devices are ignored. To become available for
        installation, the device(s) must be specified by nvdimm kickstart
        command. Also, only devices in sector mode are allowed.

        :return: a set of device names
        """
        namespaces_to_use = self.get_namespaces_to_use()
        devices_to_use = self.get_devices_to_use()
        devices_to_ignore = set()

        for ns_name, ns_info in nvdimm.namespaces.items():
            if ns_info.mode != blockdev.NVDIMMNamespaceMode.SECTOR:
                log.debug("%s / %s will be ignored - NVDIMM device is not "
                          "in sector mode", ns_name, ns_info.blockdev)
            elif ns_name not in namespaces_to_use and ns_info.blockdev not in devices_to_use:
                log.debug("%s / %s will be ignored - NVDIMM device has not been "
                          "configured to be used", ns_name, ns_info.blockdev)
            else:
                continue

            if ns_info.blockdev:
                devices_to_ignore.add(ns_info.blockdev)

        return devices_to_ignore
