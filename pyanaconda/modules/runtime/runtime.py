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
from pyanaconda.core.signal import Signal
from pyanaconda.modules.runtime.runtime_interface import RuntimeInterface
from pyanaconda.modules.runtime.kickstart import RuntimeKickstartSpecification
from pyanaconda.modules.runtime.dracut_commands import DracutCommandsModule
from pyanaconda.modules.runtime.user_interface import UIModule
from pyanaconda.modules.common.base import KickstartService
from pyanaconda.modules.common.constants.services import RUNTIME
from pyanaconda.modules.common.containers import TaskContainer
from pyanaconda.modules.common.submodule_manager import SubmoduleManager

log = get_module_logger(__name__)

__all__ = ["RuntimeService"]


class RuntimeService(KickstartService):
    """The Runtime service.

    This service provides runtime data storage on D-Bus. It must always run.
    """

    def __init__(self):
        super().__init__()

        # Initialize modules.
        self._modules = SubmoduleManager()

        self._dracut_module = DracutCommandsModule()
        self._modules.add_module(self._dracut_module)

        self._ui_module = UIModule()
        self._modules.add_module(self._ui_module)

        self.logging_host_changed = Signal()
        self._logging_host = ""

        self.logging_port_changed = Signal()
        self._logging_port = ""

        self.rescue_changed = Signal()
        self._rescue = False

        self.rescue_nomount_changed = Signal()
        self._rescue_nomount = False

        self.rescue_romount_changed = Signal()
        self._rescue_romount = False

        self.eula_agreed_changed = Signal()
        self._eula_agreed = False


    def publish(self):
        """Publish the module."""
        TaskContainer.set_namespace(RUNTIME.namespace)

        self._modules.publish_modules()

        DBus.publish_object(RUNTIME.object_path, RuntimeInterface(self))
        DBus.register_service(RUNTIME.service_name)

    @property
    def kickstart_specification(self):
        """Return the kickstart specification."""
        return RuntimeKickstartSpecification

    def process_kickstart(self, data):
        """Process the kickstart data."""
        self._modules.process_kickstart(data)
        self.set_logging_host(data.logging.host)
        self.set_logging_port(data.logging.port)
        self.set_rescue(data.rescue.rescue)
        self.set_rescue_nomount(data.rescue.nomount)
        self.set_rescue_romount(data.rescue.romount)
        self.set_eula_agreed(data.eula.agreed)

    def setup_kickstart(self, data):
        """Set up the kickstart data."""
        self._modules.setup_kickstart(data)
        data.logging.host = self._logging_host
        data.logging.port = self._logging_port
        data.rescue.rescue = self._rescue
        data.rescue.nomount = self._rescue_nomount
        data.rescue.romount = self._rescue_romount
        data.eula.agreed = self._eula_agreed

    def collect_requirements(self):
        """Return installation requirements for this module.

        :return: a list of requirements
        """
        requirements = []
        requirements.extend(self._modules.collect_requirements())
        return requirements

    @property
    def logging_host(self):
        """The host for logging.

        :return: Logging host address.
        :rtype: str
        """
        return self._logging_host

    def set_logging_host(self, host):
        """Set the host for logging.

        :param host: Host address for logging.
        :type host: str
        """
        self._logging_host = host
        self.logging_host_changed.emit()
        log.debug("Logging host set to: %s", host)

    @property
    def logging_port(self):
        """The port for logging.

        :return: Logging port number.
        :rtype: int
        """
        return self._logging_port

    def set_logging_port(self, port):
        """Set the port for logging.

        :param port: Port number for logging.
        :type port: int
        """
        self._logging_port = port
        self.logging_port_changed.emit()
        log.debug("Logging port set to: %s", port)

    @property
    def rescue(self):
        """Flag indicating whether rescue mode is enabled.

        :return: True if rescue mode is enabled, else False.
        :rtype: bool
        """
        return self._rescue

    def set_rescue(self, rescue):
        """Enable or disable rescue mode.

        :param rescue: True to enable, False to disable rescue mode.
        :type rescue: bool
        """
        self._rescue = rescue
        self.rescue_changed.emit()
        log.debug("Rescue mode set to: %s", rescue)

    @property
    def rescue_nomount(self):
        """Flag for disabling mount in rescue mode.

        :return: True if mounting is disabled in rescue mode, else False.
        :rtype: bool
        """
        return self._rescue_nomount

    def set_rescue_nomount(self, nomount):
        """Enable or disable mount in rescue mode.

        :param nomount: True to disable, False to enable mount in rescue mode.
        :type nomount: bool
        """
        self._rescue_nomount = nomount
        self.rescue_nomount_changed.emit()
        log.debug("Rescue mode nomount set to: %s", nomount)

    @property
    def rescue_romount(self):
        """Flag for read-only mount in rescue mode.

        :return: True if mount is read-only in rescue mode, else False.
        :rtype: bool
        """
        return self._rescue_romount

    def set_rescue_romount(self, romount):
        """Enable or disable read-only mount in rescue mode.

        :param romount: True to enable, False to disable read-only mount in rescue mode.
        :type romount: bool
        """
        self._rescue_romount = romount
        self.rescue_romount_changed.emit()
        log.debug("Rescue mode read-only mount set to: %s", romount)

    @property
    def eula_agreed(self):
        """Flag indicating whether EULA was agreed to.

        :return: True if EULA was agreed to, else False.
        :rtype: bool
        """
        return self._eula_agreed

    def set_eula_agreed(self, agreed):
        """Set the EULA agreement flag.

        :param agreed: True if the EULA was agreed to, else False.
        :type agreed: bool
        """
        self._eula_agreed = agreed
        self.eula_agreed_changed.emit()
        log.debug("EULA agreement set to: %s", agreed)

