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
from pyanaconda.core.dbus import DBus
from pyanaconda.modules.common.constants.objects import PAYLOAD_DEFAULT
from pyanaconda.modules.payload.payloads.payload_base import PayloadBase
from pyanaconda.modules.payload.payloads.dnf.dnf_interface import DNFHandlerInterface
from pyanaconda.modules.payload.payloads.dnf.packages.packages import PackagesHandlerModule

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class DNFHandlerModule(PayloadBase):
    """The DNF payload module."""

    def __init__(self):
        super().__init__()
        self._packages_handler = PackagesHandlerModule()

    @property
    def supported_source_types(self):
        """Get list of sources supported by DNF module."""
        # TODO: Add supported sources when implemented
        return None

    def publish_payload(self):
        """Publish the payload."""
        self._packages_handler.publish()

        DBus.publish_object(PAYLOAD_DEFAULT.object_path, DNFHandlerInterface(self))
        return PAYLOAD_DEFAULT.object_path

    def process_kickstart(self, data):
        """Process the kickstart data."""
        self._packages_handler.process_kickstart(data)

    def setup_kickstart(self, data):
        """Setup the kickstart data."""
        self._packages_handler.setup_kickstart(data)

    def pre_install_with_tasks(self):
        """Execute preparation steps.

        :return: list of tasks
        """
        # TODO: Implement this method
        pass

    def install_with_tasks(self):
        """Install the payload.

        :return: list of tasks
        """
        # TODO: Implement this method
        pass

    def post_install_with_tasks(self):
        """Execute post installation steps.

        :return: list of tasks
        """
        # TODO: Implement this method
        pass

    def set_up_sources_with_task(self):
        """Set up installation sources."""
        # TODO: Implement this method
        pass

    def tear_down_sources_with_task(self):
        """Tear down installation sources."""
        # TODO: Implement this method
        pass
