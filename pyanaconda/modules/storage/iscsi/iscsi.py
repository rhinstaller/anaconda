#
# The iSCSI module
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
from blivet.iscsi import iscsi

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.signal import Signal
from pyanaconda.dbus import DBus
from pyanaconda.modules.common.base import KickstartBaseModule
from pyanaconda.modules.common.constants.objects import ISCSI
from pyanaconda.modules.storage.constants import IscsiInterfacesMode
from pyanaconda.modules.storage.iscsi.discover import ISCSIDiscoverTask, ISCSILoginTask
from pyanaconda.modules.storage.iscsi.iscsi_interface import ISCSIInterface, ISCSIDiscoverTaskInterface

log = get_module_logger(__name__)


class ISCSIModule(KickstartBaseModule):
    """The iSCSI module."""

    def __init__(self):
        super().__init__()
        self.reload_module()

        self.initiator_changed = Signal()

        self._iscsi_data = []

    def publish(self):
        """Publish the module."""
        DBus.publish_object(ISCSI.object_path, ISCSIInterface(self))

    def reload_module(self):
        """Reload the iscsi module."""
        log.debug("Start up the iSCSI module.")
        iscsi.startup()

    @property
    def initiator(self):
        """The iSCSI initiator.

        :return: a name of the initiator
        """
        return iscsi.initiator

    def set_initiator(self, initiator):
        """Set the iSCSI initiator.

        :param initiator: a name of the initiator
        """
        if not iscsi.initiator_set:
            iscsi.initiator = initiator
            self.initiator_changed.emit()
            log.debug("The iSCSI initiator is set to '%s'.", initiator)
        else:
            log.debug("The iSCSI initiator has already been set to '%s'.", iscsi.initator)

    def can_set_initiator(self):
        """Can the initiator be set?

        Once there there are active nodes logged in the initator name can't be set.
        """
        return not iscsi.initiator_set

    def get_interface_mode(self):
        """Get the mode of interfaces used for iSCSI operations.

        returns: an instance of IscsiInterfacesMode
        """
        mode = iscsi.mode
        if mode == "none":
            return IscsiInterfacesMode.UNSET
        elif mode == "default":
            return IscsiInterfacesMode.DEFAULT
        elif mode == "bind":
            return IscsiInterfacesMode.IFACENAME
        else:
            log.error("Unknown iSCSI interface mode %s set by blivet, using UNSET", mode)
            return IscsiInterfacesMode.UNSET

    def discover_with_task(self, target, credentials, interfaces_mode):
        """Discover an iSCSI device.

        :param target: the target information
        :param credentials: the iSCSI credentials
        :param interfaces_mode: required mode specified by IscsiInterfacesMode string value
        :return: a DBus path to a task
        """
        task = ISCSIDiscoverTask(target, credentials, IscsiInterfacesMode(interfaces_mode))
        path = self.publish_task(ISCSI.namespace, task, ISCSIDiscoverTaskInterface)
        return path

    def login_with_task(self, target, credentials, node):
        """Login into an iSCSI node discovered on a target.

        :param target: the target information
        :param credentials: the iSCSI credentials
        :param node: the node information
        :return: a DBus path to a task
        """
        task = ISCSILoginTask(target, credentials, node)
        path = self.publish_task(ISCSI.namespace, task)
        return path

    def write_configuration(self, sysroot):
        """Write the configuration to sysroot."""
        log.debug("Write iSCSI configuration to %s.", sysroot)
        iscsi.write(sysroot, None)

    def process_kickstart(self, data):
        """Process the kickstart data."""
        if data.iscsiname.iscsiname:
            self.set_initiator(data.iscsiname.iscsiname)
        self._iscsi_data = data.iscsi.iscsi

    def setup_kickstart(self, data):
        """Setup the kickstart data."""
        data.iscsiname.iscsiname = self.initiator
        data.iscsi.iscsi = self._iscsi_data
