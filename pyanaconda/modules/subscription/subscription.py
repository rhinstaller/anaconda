#
# Kickstart module for subscription handling.
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
from pyanaconda.dbus import DBus
from pyanaconda.core.signal import Signal
from pyanaconda.modules.common.base import KickstartModule
from pyanaconda.modules.common.constants.services import SUBSCRIPTION
from pyanaconda.modules.subscription.subscription_interface import SubscriptionInterface
from pyanaconda.modules.subscription.kickstart import SubscriptionKickstartSpecification
from pyanaconda.modules.subscription.installation import SystemPurposeConfigurationTask
from pyanaconda.modules.subscription import system_purpose

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class SubscriptionModule(KickstartModule):
    """The Subscription module."""

    def __init__(self):
        super().__init__()
        self._valid_roles = {}
        self.role_changed = Signal()
        self._role = ""

        self._valid_slas = {}
        self.sla_changed = Signal()
        self._sla = ""

        self._valid_usage_types = {}
        self.usage_changed = Signal()
        self._usage = ""

        self.addons_changed = Signal()
        self._addons = []

        self.is_system_purpose_set_changed = Signal()
        self.role_changed.connect(self.is_system_purpose_set_changed.emit)
        self.sla_changed.connect(self.is_system_purpose_set_changed.emit)
        self.usage_changed.connect(self.is_system_purpose_set_changed.emit)
        self.addons_changed.connect(self.is_system_purpose_set_changed.emit)

        self._load_valid_values()

    def _load_valid_values(self):
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

    def publish(self):
        """Publish the module."""
        DBus.publish_object(SUBSCRIPTION.object_path, SubscriptionInterface(self))
        DBus.register_service(SUBSCRIPTION.service_name)

    @property
    def kickstart_specification(self):
        """Return the kickstart specification."""
        return SubscriptionKickstartSpecification

    def process_kickstart(self, data):
        """Process the kickstart data."""
        log.debug("Processing kickstart data...")
        # Try if any of the values in kickstart match a valid field.
        # If it does, write the valid field value instead of the value from kickstart.
        #
        # This way a value in kickstart that has a different case and/or trailing white space
        # can still be used to preselect a value in a UI instead of being marked as a custom
        # user specified value.
        self._process_role(data)
        self._process_sla(data)
        self._process_usage(data)

        # we don't have any list of valid addons and addons are not shown in the UI,
        # so we just forward the values from kickstart
        if data.syspurpose.addons:
            self.set_addons(data.syspurpose.addons)

    def _process_role(self, data):
        if data.syspurpose.role:
            role_match = system_purpose.match_field(data.syspurpose.role, self.valid_roles)
        else:
            role_match = None

        if role_match:
            log.info("role value %s from kickstart matched to know valid field %s", data.syspurpose.role, role_match)
            self.set_role(role_match)
        elif data.syspurpose.role:
            log.info("using custom role value from kickstart: %s", data.syspurpose.role)
            self.set_role(data.syspurpose.role)

    def _process_sla(self, data):
        if data.syspurpose.sla:
            sla_match = system_purpose.match_field(data.syspurpose.sla, self.valid_slas)
        else:
            sla_match = None

        if sla_match:
            log.info("SLA value %s from kickstart matched to know valid field %s", data.syspurpose.sla, sla_match)
            self.set_sla(sla_match)
        elif data.syspurpose.sla:
            log.info("using custom SLA value from kickstart: %s", data.syspurpose.sla)
            self.set_sla(data.syspurpose.sla)

    def _process_usage(self, data):
        if data.syspurpose.usage:
            usage_match = system_purpose.match_field(data.syspurpose.usage, self._valid_usage_types)
        else:
            usage_match = None

        if usage_match:
            log.info("usage value %s from kickstart matched to know valid field %s", data.syspurpose.usage, usage_match)
            self.set_usage(usage_match)
        elif data.syspurpose.usage:
            log.info("using custom usage value from kickstart: %s", data.syspurpose.usage)
            self.set_usage(data.syspurpose.usage)

    def generate_kickstart(self):
        """Return the kickstart string."""
        log.debug("Generating kickstart data...")
        data = self.get_kickstart_handler()
        data.syspurpose.role = self.role
        data.syspurpose.sla = self.sla
        data.syspurpose.usage = self.usage
        data.syspurpose.addons = self.addons
        return str(data)

    @property
    def valid_roles(self):
        """Return a list of valid roles.

        :return: list of valid roles
        :rtype: list of strings
        """
        return self._valid_roles

    @property
    def role(self):
        """Return the intended role (if any)."""
        return self._role

    def set_role(self, role):
        """Set the role."""
        self._role = role
        self.role_changed.emit()
        log.debug("Role is set to %s.", role)

    @property
    def valid_slas(self):
        """Return a list of valid SLAs.

        :return: list of valid SLAs
        :rtype: list of strings
        """
        return self._valid_slas

    @property
    def sla(self):
        """Return the intended SLA (if any)."""
        return self._sla

    def set_sla(self, sla):
        """Set the SLA."""
        self._sla = sla
        self.sla_changed.emit()
        log.debug("SLA is set to %s.", sla)

    @property
    def valid_usage_types(self):
        """Return a list of valid usage types.

        :return: list of valid usage types
        :rtype: list of strings
        """
        return self._valid_usage_types

    @property
    def usage(self):
        """Return the intended usage (if any)."""
        return self._usage

    def set_usage(self, usage):
        """Set the intended usage."""
        self._usage = usage
        self.usage_changed.emit()
        log.debug("Usage is set to %s.", usage)

    @property
    def addons(self):
        """Return list of additional layered products or features (if any)."""
        return self._addons

    def set_addons(self, addons):
        """Set the intended layered products or features."""
        self._addons = addons
        self.addons_changed.emit()
        log.debug("Addons set to %s.", addons)

    @property
    def is_system_purpose_set(self):
        """Report if system purpose will be set.

        This basically means at least one of role, SLA, usage or addons
        has a user-set non-default value.
        """
        return any((self.role, self.sla, self.usage, self.addons))

    def set_system_purpose_with_task(self, sysroot):
        """Set system purpose for the installed system with an installation task.

        FIXME: This is just a temporary method.

        :param sysroot: a path to the root of the installed system
        :return: a DBus path of an installation task
        """
        task = SystemPurposeConfigurationTask(sysroot, self.role, self.sla, self.usage, self.addons)
        path = self.publish_task(SUBSCRIPTION.namespace, task)
        return path
