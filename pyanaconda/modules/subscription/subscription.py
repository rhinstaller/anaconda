#
# Kickstart module for subscription handling.
#
# Copyright (C) 2020 Red Hat, Inc.
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
import os

from pyanaconda.core import util
from pyanaconda.core.signal import Signal

from pyanaconda.modules.common.base import KickstartService
from pyanaconda.modules.common.structures.subscription import SystemPurposeData

from pyanaconda.modules.subscription import system_purpose
from pyanaconda.modules.subscription.kickstart import SubscriptionKickstartSpecification

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class SubscriptionService(KickstartService):
    """The Subscription service."""

    def __init__(self):
        super().__init__()

        # system purpose

        self._valid_roles = []
        self._valid_slas = []
        self._valid_usage_types = []

        self._system_purpose_data = SystemPurposeData()
        self.system_purpose_data_changed = Signal()

        self._load_valid_system_purpose_values()

        # FIXME: handle rhsm.service startup in a safe manner

    @property
    def kickstart_specification(self):
        """Return the kickstart specification."""
        return SubscriptionKickstartSpecification

    def process_kickstart(self, data):
        """Process the kickstart data."""
        log.debug("Processing kickstart data...")

        # system purpose
        #
        # Try if any of the values in kickstart match a valid field.
        # If it does, write the valid field value instead of the value from kickstart.
        #
        # This way a value in kickstart that has a different case and/or trailing white space
        # can still be used to preselect a value in a UI instead of being marked as a custom
        # user specified value.
        system_purpose_data = SystemPurposeData()

        system_purpose_data.role = system_purpose.process_field(
            data.syspurpose.role,
            self.valid_roles,
            "role"
        )

        system_purpose_data.sla = system_purpose.process_field(
            data.syspurpose.sla,
            self.valid_slas,
            "sla"
        )

        system_purpose_data.usage = system_purpose.process_field(
            data.syspurpose.usage,
            self.valid_usage_types,
            "usage"
        )

        if data.syspurpose.addons:
            # As we do not have a list of valid addons available, we just use what was provided
            # by the user in kickstart verbatim.
            system_purpose_data.addons = data.syspurpose.addons

        self.set_system_purpose_data(system_purpose_data)

    def setup_kickstart(self, data):
        """Return the kickstart string."""

        # system purpose
        data.syspurpose.role = self.system_purpose_data.role
        data.syspurpose.sla = self.system_purpose_data.sla
        data.syspurpose.usage = self.system_purpose_data.usage
        data.syspurpose.addons = self.system_purpose_data.addons

    # system purpose configuration

    def _load_valid_system_purpose_values(self):
        """Load lists of valid roles, SLAs and usage types.

        About role/sla/validity:
        - an older installation image might have older list of valid fields,
          missing fields that have become valid after the image has been released
        - fields that have been valid in the past might be dropped in the future
        - there is no list of valid addons

        Due to this we need to take into account that the listing might not always be
        comprehensive and that we need to allow what might on a first glance look like
        invalid values to be written to the target system.
        """
        roles, slas, usage_types = system_purpose.get_valid_fields()
        self._valid_roles = roles
        self._valid_slas = slas
        self._valid_usage_types = usage_types

    @property
    def valid_roles(self):
        """Return a list of valid roles.

        :return: list of valid roles
        :rtype: list of strings
        """
        return self._valid_roles

    @property
    def valid_slas(self):
        """Return a list of valid SLAs.

        :return: list of valid SLAs
        :rtype: list of strings
        """
        return self._valid_slas

    @property
    def valid_usage_types(self):
        """Return a list of valid usage types.

        :return: list of valid usage types
        :rtype: list of strings
        """
        return self._valid_usage_types

    @property
    def system_purpose_data(self):
        """System purpose data.

        A DBus structure holding information about system purpose,
        such as role, sla, usage and addons.

        :return: system purpose DBus structure
        :rtype: DBusData instance
        """
        return self._system_purpose_data

    def set_system_purpose_data(self, system_purpose_data):
        """Set system purpose data.

        Set the complete DBus structure containing system purpose data.

        :param system_purpose_data: system purpose data structure to be set
        :type system_purpose_data: DBus structure
        """
        self._system_purpose_data = system_purpose_data
        self.system_purpose_data_changed.emit()
        log.debug("System purpose data set to %s.", system_purpose_data)
