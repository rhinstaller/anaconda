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
from pyanaconda.modules.storage.iscsi.discover import ISCSIDiscoverTask
from pyanaconda.modules.storage.iscsi.iscsi_interface import ISCSIInterface

log = get_module_logger(__name__)


class ISCSIModule(KickstartBaseModule):
    """The iSCSI module."""

    def __init__(self):
        super().__init__()
        self.reload_module()

        self._initiator = ""
        self.initiator_changed = Signal()

        self._iscsi_data = list()

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
        return self._initiator

    def set_initiator(self, initiator):
        """Set the iSCSI initiator.

        :param initiator: a name of the initiator
        """
        self._initiator = initiator
        self.initiator_changed.emit()
        log.debug("The iSCSI initiator is set to '%s'.", initiator)

    def discover_with_task(self, target, credentials):
        """Discover an iSCSI device.

        :param target: the target information
        :param credentials: the iSCSI credentials
        :return: a DBus path to a task
        """
        task = ISCSIDiscoverTask(target, credentials)
        path = self.publish_task(ISCSI.namespace, task)
        return path

    def write_configuration(self, sysroot):
        """Write the configuration to sysroot."""
        log.debug("Write iSCSI configuration to %s.", sysroot)
        iscsi.write(sysroot, None)

    def process_kickstart(self, data):
        """Process the kickstart data."""
        self.set_initiator(data.iscsiname.iscsiname)
        self._iscsi_data = data.iscsi.iscsi

    def setup_kickstart(self, data):
        """Setup the kickstart data."""
        data.iscsiname.iscsiname = self.initiator
        data.iscsi.iscsi = self._iscsi_data
