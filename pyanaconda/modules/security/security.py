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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import shlex

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.dbus import DBus
from pyanaconda.core.kernel import kernel_arguments
from pyanaconda.core.signal import Signal
from pyanaconda.modules.common.base import KickstartService
from pyanaconda.modules.common.constants.services import SECURITY
from pyanaconda.modules.common.containers import TaskContainer
from pyanaconda.modules.common.structures.realm import RealmData
from pyanaconda.modules.common.structures.requirement import Requirement
from pyanaconda.modules.common.submodule_manager import SubmoduleManager
from pyanaconda.modules.security.certificates import CertificatesModule
from pyanaconda.modules.security.constants import SELinuxMode
from pyanaconda.modules.security.installation import (
    AUTHSELECT_ARGS,
    ConfigureAuthselectTask,
    ConfigureFingerprintAuthTask,
    ConfigureFIPSTask,
    ConfigureSELinuxTask,
    PreconfigureFIPSTask,
    RealmDiscoverTask,
    RealmJoinTask,
)
from pyanaconda.modules.security.kickstart import SecurityKickstartSpecification
from pyanaconda.modules.security.security_interface import SecurityInterface

log = get_module_logger(__name__)


class SecurityService(KickstartService):
    """The Security service."""

    def __init__(self):
        super().__init__()

        # Initialize modules.
        self._modules = SubmoduleManager()

        self._certificates_module = CertificatesModule()
        self._modules.add_module(self._certificates_module)

        self.selinux_changed = Signal()
        self._selinux = SELinuxMode.DEFAULT

        self.authselect_changed = Signal()
        self._authselect_args = []

        self.fingerprint_auth_enabled_changed = Signal()
        self._fingerprint_auth_enabled = False

        self.realm_changed = Signal()
        self._realm = RealmData()

    def publish(self):
        """Publish the module."""
        TaskContainer.set_namespace(SECURITY.namespace)

        self._modules.publish_modules()

        DBus.publish_object(SECURITY.object_path, SecurityInterface(self))
        DBus.register_service(SECURITY.service_name)

    @property
    def kickstart_specification(self):
        """Return the kickstart specification."""
        return SecurityKickstartSpecification

    def process_kickstart(self, data):
        """Process the kickstart data."""
        self._modules.process_kickstart(data)

        if data.selinux.selinux is not None:
            self.set_selinux(SELinuxMode(data.selinux.selinux))

        if data.authselect.authselect:
            self.set_authselect(shlex.split(data.authselect.authselect))

        if data.realm.join_realm:
            realm = RealmData()
            realm.name = data.realm.join_realm
            realm.discover_options = data.realm.discover_options
            realm.join_options = data.realm.join_args

            self.set_realm(realm)

    def setup_kickstart(self, data):
        """Set up the kickstart data."""
        self._modules.setup_kickstart(data)

        if self.selinux != SELinuxMode.DEFAULT:
            data.selinux.selinux = self.selinux.value

        if self.authselect:
            data.authselect.authselect = " ".join(self.authselect)
        elif self.fingerprint_auth_enabled:
            data.authselect.authselect = " ".join(AUTHSELECT_ARGS)

        if self.realm.name:
            data.realm.join_realm = self.realm.name
            data.realm.discover_options = self.realm.discover_options
            data.realm.join_args = self.realm.join_options

    @property
    def fips_enabled(self):
        """Is FIPS enabled?

        :return: True or False
        """
        return kernel_arguments.is_enabled("fips")

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
    def fingerprint_auth_enabled(self):
        """Specifies if fingerprint authentication should be enabled.

        :return: True if fingerprint authentication should be enabled, False otherwise
        :rtype: bool
        """
        return self._fingerprint_auth_enabled

    def set_fingerprint_auth_enabled(self, fingerprint_auth_enabled):
        """Set if fingerprint authentication should be enabled.

        :param bool fingerprint_auth_enabled: True if fingerprint authentication
                                              should be enabled, False otherwise
        """
        self._fingerprint_auth_enabled = fingerprint_auth_enabled
        self.fingerprint_auth_enabled_changed.emit()
        log.debug("Fingerprint authentication enabled is set to %s.",
                  self.fingerprint_auth_enabled)

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

    def handle_realm_discover_results(self, realm_data):
        """ Handle results from the RealmDiscover task.

        :param realm_data: an updated instance of realm data
        """
        log.debug("Updating realm data with results from realm discover task.")
        self.set_realm(realm_data)

    def collect_requirements(self):
        """Return installation requirements for this module.

        :return: a list of requirements
        """
        requirements = []

        # Add FIPS requirements.
        if self.fips_enabled:
            requirements.append(Requirement.for_package(
                "crypto-policies-scripts",
                reason="Required for FIPS compliance."
            ))

        # Add realm requirements.
        for name in self.realm.required_packages:
            requirements.append(Requirement.for_package(
                name, reason="Needed to join a realm."
            ))

        # Add authselect requirements
        if self.authselect or self.fingerprint_auth_enabled:
            # we need the authselect package in two cases:
            # - autselect command is used in kickstart
            # - to configure fingerprint authentication
            requirements.append(Requirement.for_package(
                "authselect",
                reason="Needed by authselect kickstart command & "
                "for fingerprint authentication support."
            ))

        return requirements

    def discover_realm_with_task(self):
        """Return the setup task for discovering a realm."""
        realm_task = RealmDiscoverTask(sysroot=conf.target.system_root,
                                       realm_data=self.realm)

        realm_task.succeeded_signal.connect(
            lambda: self.handle_realm_discover_results(realm_task.get_result())
        )
        return realm_task

    def join_realm_with_task(self):
        """Return the setup task for joining a realm."""
        realm_task = RealmJoinTask(sysroot=conf.target.system_root, realm_data=self.realm)

        # Connect to realm-data-changed signal, so that the realm data in the
        # realm-join task is always up to date.
        self.realm_changed.connect(lambda: realm_task.set_realm_data(self.realm))
        return realm_task

    def preconfigure_fips_with_task(self, payload_type):
        """Set up FIPS for the payload installation with a task.

        :param payload_type: a string with the payload type
        :return: an installation task
        """
        return PreconfigureFIPSTask(
            sysroot=conf.target.system_root,
            payload_type=payload_type,
            fips_enabled=self.fips_enabled
        )

    def configure_fips_with_task(self):
        """Configure FIPS on the installed system.

        :return: an installation task
        """
        return ConfigureFIPSTask(
            sysroot=conf.target.system_root,
            fips_enabled=self.fips_enabled
        )

    def install_with_tasks(self):
        """Return the installation tasks of this module.

        :returns: list of installation tasks
        """
        return [
            ConfigureSELinuxTask(
                sysroot=conf.target.system_root,
                selinux_mode=self.selinux
            ),
            ConfigureFingerprintAuthTask(
                sysroot=conf.target.system_root,
                fingerprint_auth_enabled=self.fingerprint_auth_enabled
            ),
            ConfigureAuthselectTask(
                sysroot=conf.target.system_root,
                authselect_options=self.authselect
            )
        ]
