#
# DBus errors related to the configuration.
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


@dbus_error("ConfigurationError", namespace=ANACONDA_NAMESPACE)
class ConfigurationError(AnacondaError):
    """General exception for the configuration errors."""
    pass


@dbus_error("StorageDiscoveryError", namespace=ANACONDA_NAMESPACE)
class StorageDiscoveryError(ConfigurationError):
    """Exception for storage discovery errors."""
    pass


@dbus_error("StorageConfigurationError", namespace=ANACONDA_NAMESPACE)
class StorageConfigurationError(ConfigurationError):
    """Exception for storage configuration errors."""
    pass


@dbus_error("BootloaderConfigurationError", namespace=ANACONDA_NAMESPACE)
class BootloaderConfigurationError(ConfigurationError):
    """Exception for bootloader configuration errors."""
    pass


@dbus_error("KeyboardConfigurationError", namespace=ANACONDA_NAMESPACE)
class KeyboardConfigurationError(ConfigurationError):
    """Exception for keyboard configuration errors."""
    pass
