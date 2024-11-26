#
# DBus errors related to the installation.
#
# Copyright (C) 2018  Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
from pyanaconda.core.dbus import dbus_error
from pyanaconda.modules.common.constants.namespaces import ANACONDA_NAMESPACE
from pyanaconda.modules.common.errors.general import AnacondaError


@dbus_error("InstallationError", namespace=ANACONDA_NAMESPACE)
class InstallationError(AnacondaError):
    """General exception for the installation errors."""
    pass


@dbus_error("NonCriticalInstallationError", namespace=ANACONDA_NAMESPACE)
class NonCriticalInstallationError(AnacondaError):
    """Exception for the non-critical installation errors."""
    pass


@dbus_error("LanguageInstallationError", namespace=ANACONDA_NAMESPACE)
class LanguageInstallationError(InstallationError):
    """Exception for the language installation errors."""
    pass


@dbus_error("KeyboardInstallationError", namespace=ANACONDA_NAMESPACE)
class KeyboardInstallationError(InstallationError):
    """Exception for the keyboard installation errors."""
    pass


@dbus_error("NetworkInstallationError", namespace=ANACONDA_NAMESPACE)
class NetworkInstallationError(InstallationError):
    """Exception for the network installation errors."""
    pass


@dbus_error("FirewallConfigurationError", namespace=ANACONDA_NAMESPACE)
class FirewallConfigurationError(InstallationError):
    """Exception for the firewall configuration errors."""
    pass


@dbus_error("TimezoneConfigurationError", namespace=ANACONDA_NAMESPACE)
class TimezoneConfigurationError(InstallationError):
    """Exception for the timezone configuration errors."""
    pass


@dbus_error("SecurityInstallationError", namespace=ANACONDA_NAMESPACE)
class SecurityInstallationError(InstallationError):
    """Exception for the security installation errors."""
    pass


@dbus_error("BootloaderInstallationError", namespace=ANACONDA_NAMESPACE)
class BootloaderInstallationError(InstallationError):
    """Exception for the bootloader installation errors."""
    pass


@dbus_error("StorageInstallationError", namespace=ANACONDA_NAMESPACE)
class StorageInstallationError(InstallationError):
    """Exception for the storage installation errors."""
    pass


@dbus_error("PayloadInstallationError", namespace=ANACONDA_NAMESPACE)
class PayloadInstallationError(InstallationError):
    """Exception for the payload installation errors."""
    pass


@dbus_error("InsightsClientMissingError", namespace=ANACONDA_NAMESPACE)
class InsightsClientMissingError(InstallationError):
    """Exception for missing Red Hat Insights utility."""
    pass


@dbus_error("InsightsConnectError", namespace=ANACONDA_NAMESPACE)
class InsightsConnectError(InstallationError):
    """Exception for error when connecting to Red Hat Insights."""
    pass


@dbus_error("SubscriptionTokenTransferError", namespace=ANACONDA_NAMESPACE)
class SubscriptionTokenTransferError(InstallationError):
    """Exception for errors during subscription token transfer."""
    pass


@dbus_error("TargetSatelliteProvisioningError", namespace=ANACONDA_NAMESPACE)
class TargetSatelliteProvisioningError(InstallationError):
    """Exception for errors when provisioning target system for Satellite."""
    pass
