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
from blivet import udev
from blivet.devices import NVDIMMNamespaceDevice
from blivet.static_data import nvdimm
from pykickstart.constants import NVDIMM_ACTION_RECONFIGURE, NVDIMM_ACTION_USE

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.dbus import DBus
from pyanaconda.modules.common.base import KickstartBaseModule
from pyanaconda.modules.common.constants.objects import NVDIMM
from pyanaconda.modules.common.errors.storage import UnavailableStorageError
from pyanaconda.modules.storage.nvdimm.nvdimm_interface import NVDIMMInterface
from pyanaconda.modules.storage.nvdimm.reconfigure import NVDIMMReconfigureTask

gi.require_version("BlockDev", "2.0")
from gi.repository import BlockDev as blockdev

log = get_module_logger(__name__)

__all__ = ["NVDIMMModule"]


class NVDIMMModule(KickstartBaseModule):
    """The NVDIMM module."""

    def __init__(self):
        super().__init__()
        self._storage = None
        self._actions = list()

    def publish(self):
        """Publish the module."""
        DBus.publish_object(NVDIMM.object_path, NVDIMMInterface(self))

    def is_supported(self):
        """Is this module supported?"""
        return True

    @property
    def storage(self):
        """The storage model.

        :return: an instance of Blivet
        :raise: UnavailableStorageError if not available
        """
        if self._storage is None:
            raise UnavailableStorageError()

        return self._storage

    def on_storage_changed(self, storage):
        """Keep the instance of the current storage."""
        self._storage = storage

    def process_kickstart(self, data):
        """Process the kickstart data."""
        self._actions = data.nvdimm.actionList

    def setup_kickstart(self, data):
        """Setup the kickstart data."""
        namespaces = self.get_used_namespaces()
        self.set_namespaces_to_use(namespaces)
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

        Don't ignore devices that have an iso9660 file system. We might
        want to use them as an installation source.

        :return: a set of device names
        """
        namespaces_to_use = self.get_namespaces_to_use()
        devices_to_use = self.get_devices_to_use()
        devices_to_ignore = set()

        for ns_name, ns_info in nvdimm.namespaces.items():
            # this is happening when namespace is set to DEVDAX mode - block device is not present
            if ns_info.blockdev is None:
                log.debug("%s will be skipped - NVDIMM namespace block device information "
                          "can't be retrieved", ns_name)
                continue

            info = udev.get_device(device_node="/dev/" + ns_info.blockdev)

            if info and udev.device_get_format(info) == "iso9660":
                log.debug("%s / %s won't be ignored - NVDIMM device has "
                          "an iso9660 file system", ns_name, ns_info.blockdev)
                continue
            elif ns_info.mode != blockdev.NVDIMMNamespaceMode.SECTOR:
                log.debug("%s / %s will be ignored - NVDIMM device is not "
                          "in sector mode", ns_name, ns_info.blockdev)
            elif ns_name not in namespaces_to_use and ns_info.blockdev not in devices_to_use:
                log.debug("%s / %s will be ignored - NVDIMM device has not been "
                          "configured to be used", ns_name, ns_info.blockdev)
            else:
                continue

            devices_to_ignore.add(ns_info.blockdev)

        return devices_to_ignore

    def create_action(self):
        """Create a new action.

        FIXME: Don't use kickstart data.

        :return: an instance of an action
        """
        from pyanaconda.core.kickstart.commands import NvdimmData
        action = NvdimmData()
        return action

    def find_action(self, namespace):
        """Find an action by the namespace.

        :param namespace: a name of the namespace
        :return: an instance of an action with the same namespace
        """
        if not namespace:
            return None

        for action in self._actions:
            if action.namespace == namespace:
                return action

        return None

    def update_action(self, namespace, mode, sector_size):
        """Update an action.

        :param namespace: a device name of a namespace
        :param mode: a mode
        :param sector_size: a sector size
        :return: an instance of the updated action
        """
        action = self.find_action(namespace)

        if not action:
            action = self.create_action()
            self._actions.append(action)

        action.action = NVDIMM_ACTION_RECONFIGURE
        action.namespace = namespace
        action.mode = mode
        action.sectorsize = sector_size
        return action

    def get_used_namespaces(self):
        """Get a list of namespaces that are used for the installation.

        :return: a list of namespaces
        """
        return [
            d.devname for d in self.storage.disks
            if isinstance(d, NVDIMMNamespaceDevice)
        ]

    def set_namespaces_to_use(self, namespaces):
        """Set namespaces to use.

        Updates "nvdimm use" commands.  Doesn't add use command for devices which
        are reconfigured with "nvdimm reconfigure" because reconfigure in kickstart
        implies use.

        :param namespaces: a list of namespaces
        :return: a list of actions
        """
        log.debug("Setting namespaces to use to: %s", namespaces)

        # Keep the reconfiguration actions.
        reconfigure_actions = [
            action for action in self._actions
            if action.action == NVDIMM_ACTION_RECONFIGURE
        ]

        namespaces_to_configure = {
            action.namespace for action in reconfigure_actions
        }

        # Create new use actions.
        use_actions = []
        namespaces_to_use = sorted(namespaces)

        for namespace in namespaces_to_use:
            # Reconfigured namespaces are used implicitly.
            if namespace in namespaces_to_configure:
                continue

            action = self.create_action()
            action.action = NVDIMM_ACTION_USE
            action.namespace = namespace
            use_actions.append(action)

        # Update the current actions.
        self._actions = reconfigure_actions + use_actions
        return self._actions

    def reconfigure_with_task(self, namespace, mode, sector_size):
        """Reconfigure a namespace.

        :param namespace: a device name of a namespace (e.g. 'namespace0.0')
        :param mode: a new mode (one of 'sector', 'memory', 'dax')
        :param sector_size: a sector size for the sector mode
        :return: a task
        """
        task = NVDIMMReconfigureTask(namespace, mode, sector_size)
        task.succeeded_signal.connect(lambda: self.update_action(namespace, mode, sector_size))
        return task
