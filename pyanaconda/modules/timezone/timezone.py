#
# Kickstart module for date and time settings.
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
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.dbus import DBus
from pyanaconda.core.signal import Signal
from pyanaconda.modules.common.base import KickstartService
from pyanaconda.modules.common.constants.services import TIMEZONE
from pyanaconda.timezone import NTP_PACKAGE
from pyanaconda.modules.common.containers import TaskContainer
from pyanaconda.modules.common.structures.requirement import Requirement
from pyanaconda.modules.timezone.installation import ConfigureNTPTask, ConfigureTimezoneTask
from pyanaconda.modules.timezone.kickstart import TimezoneKickstartSpecification
from pyanaconda.modules.timezone.timezone_interface import TimezoneInterface

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class TimezoneService(KickstartService):
    """The Timezone service."""

    def __init__(self):
        super().__init__()
        self.timezone_changed = Signal()
        self._timezone = "America/New_York"

        self.is_utc_changed = Signal()
        self._is_utc = False

        self.ntp_enabled_changed = Signal()
        self._ntp_enabled = True

        self.ntp_servers_changed = Signal()
        self._ntp_servers = []

    def publish(self):
        """Publish the module."""
        TaskContainer.set_namespace(TIMEZONE.namespace)
        DBus.publish_object(TIMEZONE.object_path, TimezoneInterface(self))
        DBus.register_service(TIMEZONE.service_name)

    @property
    def kickstart_specification(self):
        """Return the kickstart specification."""
        return TimezoneKickstartSpecification

    def process_kickstart(self, data):
        """Process the kickstart data."""
        self.set_timezone(data.timezone.timezone)
        self.set_is_utc(data.timezone.isUtc)
        self.set_ntp_enabled(not data.timezone.nontp)
        self.set_ntp_servers(data.timezone.ntpservers)

    def setup_kickstart(self, data):
        """Set up the kickstart data."""
        data.timezone.timezone = self.timezone
        data.timezone.isUtc = self.is_utc
        data.timezone.nontp = not self.ntp_enabled

        if self.ntp_enabled:
            data.timezone.ntpservers = list(self.ntp_servers)

    @property
    def timezone(self):
        """Return the timezone."""
        return self._timezone

    def set_timezone(self, timezone):
        """Set the timezone."""
        self._timezone = timezone
        self.timezone_changed.emit()
        log.debug("Timezone is set to %s.", timezone)

    @property
    def is_utc(self):
        """Is the hardware clock set to UTC?"""
        return self._is_utc

    def set_is_utc(self, is_utc):
        """Set if the hardware clock is set to UTC."""
        self._is_utc = is_utc
        self.is_utc_changed.emit()
        log.debug("UTC is set to %s.", is_utc)

    @property
    def ntp_enabled(self):
        """Enable automatic starting of NTP service."""
        return self._ntp_enabled

    def set_ntp_enabled(self, ntp_enabled):
        """Enable or disable automatic starting of NTP service."""
        self._ntp_enabled = ntp_enabled
        self.ntp_enabled_changed.emit()
        log.debug("NTP is set to %s.", ntp_enabled)

    @property
    def ntp_servers(self):
        """Return a list of NTP servers."""
        return self._ntp_servers

    def set_ntp_servers(self, servers):
        """Set NTP servers."""
        self._ntp_servers = list(servers)
        self.ntp_servers_changed.emit()
        log.debug("NTP servers are set to %s.", servers)

    def collect_requirements(self):
        """Return installation requirements for this module.

        :return: a list of requirements
        """
        requirements = []

        # Add ntp service requirements.
        if self._ntp_enabled:
            requirements.append(
                Requirement.for_package(NTP_PACKAGE, reason="Needed to run NTP service.")
            )

        return requirements

    def install_with_tasks(self):
        """Return the installation tasks of this module.

        :return: list of installation tasks
        """
        return [
            ConfigureTimezoneTask(
                sysroot=conf.target.system_root,
                timezone=self.timezone,
                is_utc=self.is_utc
            ),
            ConfigureNTPTask(
                sysroot=conf.target.system_root,
                ntp_enabled=self.ntp_enabled,
                ntp_servers=self.ntp_servers
            )
        ]
