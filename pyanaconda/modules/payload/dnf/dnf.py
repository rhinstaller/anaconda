#
# Kickstart module for DNF payload.
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
from pyanaconda.dbus import DBus
from pyanaconda.modules.common.base import KickstartBaseModule
from pyanaconda.modules.common.constants.objects import PAYLOAD_DEFAULT
from pyanaconda.modules.payload.dnf.dnf_interface import DNFHandlerInterface
from pyanaconda.modules.payload.payload_data import PayloadData

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class DNFHandlerModule(KickstartBaseModule):
    """The DNF payload module."""

    def __init__(self):
        super().__init__()
        self._payload_data = PayloadData()

    def publish(self):
        """Publish the module."""
        DBus.publish_object(PAYLOAD_DEFAULT.object_path, DNFHandlerInterface(self))

    def packages_list(self):
        return self._packages_data.package_list

    def set_package_list(self, package_list):
        self._packages_data.package_list = package_list
        self.package_list_changed.emit()
        log.debug("Package list is set to '%s'.", package_list)

    def process_kickstart(self, data):
        """Process the kickstart data."""
        pass

    def setup_kickstart(self):
        """Setup the kickstart data."""
        pass
