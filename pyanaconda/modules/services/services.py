#
# Kickstart module for the services.
#
# Copyright (C) 2018 Red Hat, Inc.
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
from pykickstart.constants import FIRSTBOOT_DEFAULT, FIRSTBOOT_SKIP, FIRSTBOOT_RECONFIG

from pyanaconda.core.constants import TEXT_ONLY_TARGET, GRAPHICAL_TARGET
from pyanaconda.dbus import DBus
from pyanaconda.core.signal import Signal
from pyanaconda.modules.common.base import KickstartModule
from pyanaconda.modules.common.constants.services import SERVICES
from pyanaconda.modules.services.constants import SetupOnBootAction
from pyanaconda.modules.services.kickstart import ServicesKickstartSpecification
from pyanaconda.modules.services.services_interface import ServicesInterface


from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class ServicesModule(KickstartModule):
    """The Services module."""

    def __init__(self):
        super().__init__()
        self.enabled_services_changed = Signal()
        self._enabled_services = list()

        self.disabled_services_changed = Signal()
        self._disabled_services = list()

        self.default_target_changed = Signal()
        self._default_target = ""

        self.default_desktop_changed = Signal()
        self._default_desktop = ""

        self.setup_on_boot_changed = Signal()
        self._setup_on_boot = SetupOnBootAction.DEFAULT

    def publish(self):
        """Publish the module."""
        DBus.publish_object(SERVICES.object_path, ServicesInterface(self))
        DBus.register_service(SERVICES.service_name)

    @property
    def kickstart_specification(self):
        """Return the kickstart specification."""
        return ServicesKickstartSpecification

    def process_kickstart(self, data):
        """Process the kickstart data."""
        log.debug("Processing kickstart data...")
        self.set_enabled_services(data.services.enabled)
        self.set_disabled_services(data.services.disabled)

        if data.skipx.skipx:
            self.set_default_target(TEXT_ONLY_TARGET)
        elif data.xconfig.startX:
            self.set_default_target(GRAPHICAL_TARGET)

        self.set_default_desktop(data.xconfig.defaultdesktop)

        setup_on_boot = self._map_firstboot(data.firstboot.firstboot)
        self.set_setup_on_boot(setup_on_boot)

    def generate_kickstart(self):
        """Return the kickstart string."""
        log.debug("Generating kickstart data...")
        data = self.get_kickstart_handler()

        data.services.enabled = self.enabled_services
        data.services.disabled = self.disabled_services

        if self.default_target == TEXT_ONLY_TARGET:
            data.skipx.skipx = True
        elif self.default_target == GRAPHICAL_TARGET:
            data.xconfig.startX = True

        data.xconfig.defaultdesktop = self.default_desktop

        firstboot = self._map_firstboot(self.setup_on_boot, reverse=True)
        data.firstboot.firstboot = firstboot

        return str(data)

    def _map_firstboot(self, value, reverse=False):
        """Convert the firstboot value to the setup on boot value.

        :param value: a value of the action
        :param reverse: reverse the direction
        :return: a converted value of the action
        """
        mapping = {
            None: SetupOnBootAction.DEFAULT,
            FIRSTBOOT_SKIP: SetupOnBootAction.DISABLED,
            FIRSTBOOT_DEFAULT: SetupOnBootAction.ENABLED,
            FIRSTBOOT_RECONFIG: SetupOnBootAction.RECONFIG,
        }

        if reverse:
            mapping = {v: k for k, v in mapping.items()}

        return mapping[value]

    @property
    def enabled_services(self):
        """List of enabled services."""
        return self._enabled_services

    def set_enabled_services(self, services):
        """Set the enabled services.

        :param services: a list of service names
        """
        self._enabled_services = list(services)
        self.enabled_services_changed.emit()
        log.debug("Enabled services are set to %s.", services)

    @property
    def disabled_services(self):
        """List of disabled services."""
        return self._disabled_services

    def set_disabled_services(self, services):
        """Set the disabled services.

        :param services: a list of service names
        """
        self._disabled_services = list(services)
        self.disabled_services_changed.emit()
        log.debug("Disabled services are set to %s.", services)

    @property
    def default_target(self):
        """Default target of the installed system."""
        return self._default_target

    def set_default_target(self, target):
        """Set the default target of the installed system.

        :param target: a string with the target
        """
        self._default_target = target
        self.default_target_changed.emit()
        log.debug("Default target is set to %s.", target)

    @property
    def default_desktop(self):
        """Default desktop of the installed system."""
        return self._default_desktop

    def set_default_desktop(self, desktop):
        """Set the default desktop of the installed system.

        :param desktop: a string with the desktop
        """
        self._default_desktop = desktop
        self.default_desktop_changed.emit()
        log.debug("Default desktop is set to %s.", desktop)

    @property
    def setup_on_boot(self):
        """Set up the installed system on the first boot."""
        return self._setup_on_boot

    def set_setup_on_boot(self, value):
        """Set up the installed system on the first boot.

        :param value: an action
        """
        self._setup_on_boot = value
        self.setup_on_boot_changed.emit()
        log.debug("Setup on boot is set to %s.", value)
