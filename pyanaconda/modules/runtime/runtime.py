#
# Kickstart module for general and flow control settings.
#
# Copyright (C) 2023 Red Hat, Inc.
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
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.dbus import DBus
from pyanaconda.modules.runtime.runtime_interface import RuntimeInterface
from pyanaconda.modules.common.base import KickstartService
from pyanaconda.modules.common.constants.services import RUNTIME
from pyanaconda.modules.common.containers import TaskContainer

log = get_module_logger(__name__)

__all__ = ["RuntimeService"]


class RuntimeService(KickstartService):
    """The Runtime service.

    This service provides runtime data storage on D-Bus. It must always run.
    """

    # def __init__(self):
    #     super().__init__()

    def publish(self):
        """Publish the module."""
        TaskContainer.set_namespace(RUNTIME.namespace)

        DBus.publish_object(RUNTIME.object_path, RuntimeInterface(self))
        DBus.register_service(RUNTIME.service_name)

    @property
    def kickstart_specification(self):
        """Return the kickstart specification."""
        return None

    def process_kickstart(self, data):
        """Process the kickstart data."""
        pass

    def setup_kickstart(self, data):
        """Set up the kickstart data."""
        pass

    def collect_requirements(self):
        """Return installation requirements for this module.

        :return: a list of requirements
        """
        requirements = []
        return requirements
