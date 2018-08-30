#
# Kickstart module for security.
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
import shlex

from pyanaconda.dbus import DBus
from pyanaconda.core.signal import Signal
from pyanaconda.modules.common.base import KickstartModule
from pyanaconda.modules.common.constants.services import SECURITY
from pyanaconda.modules.common.structures.realm import RealmData
from pyanaconda.modules.security.constants import SELinuxMode
from pyanaconda.modules.security.kickstart import SecurityKickstartSpecification
from pyanaconda.modules.security.security_interface import SecurityInterface

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class SecurityModule(KickstartModule):
    """The Security module."""

    def __init__(self):
        super().__init__()

        self.selinux_changed = Signal()
        self._selinux = SELinuxMode.DEFAULT

        self.authselect_changed = Signal()
        self._authselect_args = []

        self.authconfig_changed = Signal()
        self._authconfig_args = []

        self.realm_changed = Signal()
        self._realm = self.create_realm()

    def publish(self):
        """Publish the module."""
        DBus.publish_object(SECURITY.object_path, SecurityInterface(self))
        DBus.register_service(SECURITY.service_name)

    @property
    def kickstart_specification(self):
        """Return the kickstart specification."""
        return SecurityKickstartSpecification

    def process_kickstart(self, data):
        """Process the kickstart data."""
        log.debug("Processing kickstart data...")

        if data.selinux.selinux is not None:
            self.set_selinux(SELinuxMode(data.selinux.selinux))

        if data.authselect.authselect:
            self.set_authselect(shlex.split(data.authselect.authselect))

        if data.authconfig.authconfig:
            self.set_authconfig(shlex.split(data.authconfig.authconfig))

        if data.realm.join_realm:

            realm = self.create_realm()
            realm.name = data.realm.join_realm
            realm.discover_options = data.realm.discover_options
            realm.join_options = data.realm.join_args

            self.set_realm(realm)

    def generate_kickstart(self):
        """Return the kickstart string."""
        log.debug("Generating kickstart data...")
        data = self.get_kickstart_handler()

        if self.selinux != SELinuxMode.DEFAULT:
            data.selinux.selinux = self.selinux.value

        if self.authselect:
            data.authselect.authselect = " ".join(self.authselect)

        if self.authconfig:
            data.authconfig.authconfig = " ".join(self.authconfig)

        if self.realm.name:
            data.realm.join_realm = self.realm.name
            data.realm.discover_options = self.realm.discover_options
            data.realm.join_args = self.realm.join_options

        return str(data)

    @property
    def selinux(self):
        """The state of SELinux on the installed system.

        :return: an instance of SELinuxMode
        """
        return self._selinux

    def set_selinux(self, value):
        """Sets the state of SELinux on the installed system.

        :param value: an instance of SELinuxMode
        """
        self._selinux = value
        self.selinux_changed.emit()
        log.debug("SElinux is set to %s.", value)

    @property
    def authselect(self):
        """Arguments for the authselect tool.

        :return: a list of arguments
        """
        return self._authselect_args

    def set_authselect(self, args):
        """Set the arguments for the authselect tool.

        :param args: a list of arguments
        """
        self._authselect_args = args
        self.authselect_changed.emit()
        log.debug("Authselect is set to %s.", args)

    @property
    def authconfig(self):
        """Arguments for the authconfig tool.

        Authconfig is deprecated, use authselect.

        :return: a list of arguments
        """
        return self._authconfig_args

    def set_authconfig(self, args):
        """Set the arguments for the authconfig tool.

        Authconfig is deprecated, use authselect.

        :param args: a list of arguments
        """
        self._authconfig_args = args
        self.authconfig_changed.emit()
        log.debug("Authconfig is set to %s.", args)

    @property
    def realm(self):
        """Specification of the enrollment in a realm.

        :return: an instance of RealmData
        """
        return self._realm

    def set_realm(self, realm):
        """Specify of the enrollment in a realm.

        :param realm: an instance of RealmData
        """
        self._realm = realm
        self.realm_changed.emit()
        log.debug("Realm is set to %s.", realm)

    def create_realm(self):
        """Create a new instance of realm data.

        :return: an instance of RealmData
        """
        return RealmData()
