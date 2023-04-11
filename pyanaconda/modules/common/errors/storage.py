#
# DBus errors related to the storage.
#
# Copyright (C) 2019  Red Hat, Inc.  All rights reserved.
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
from pyanaconda.modules.common.constants.namespaces import STORAGE_NAMESPACE
from pyanaconda.modules.common.errors.general import AnacondaError


@dbus_error("UnavailableStorageError", namespace=STORAGE_NAMESPACE)
class UnavailableStorageError(AnacondaError):
    """The storage model is not available."""
    pass


@dbus_error("UnavailableDataError", namespace=STORAGE_NAMESPACE)
class UnavailableDataError(AnacondaError):
    """The data are not available."""
    pass


@dbus_error("UnusableStorageError", namespace=STORAGE_NAMESPACE)
class UnusableStorageError(AnacondaError):
    """The storage model is not usable."""
    pass


@dbus_error("InvalidStorageError", namespace=STORAGE_NAMESPACE)
class InvalidStorageError(AnacondaError):
    """The storage model is not valid."""
    pass


@dbus_error("UnsupportedPartitioningError", namespace=STORAGE_NAMESPACE)
class UnsupportedPartitioningError(AnacondaError):
    """The partitioning method is not supported."""
    pass


@dbus_error("UnsupportedDeviceError", namespace=STORAGE_NAMESPACE)
class UnsupportedDeviceError(AnacondaError):
    """The device is not supported."""
    pass


@dbus_error("UnknownDeviceError", namespace=STORAGE_NAMESPACE)
class UnknownDeviceError(AnacondaError):
    """The device is not recognized."""
    pass


@dbus_error("ProtectedDeviceError", namespace=STORAGE_NAMESPACE)
class ProtectedDeviceError(AnacondaError):
    """The device is protected."""
    pass


@dbus_error("MountFilesystemError", namespace=STORAGE_NAMESPACE)
class MountFilesystemError(AnacondaError):
    """Failed to un/mount a filesystem."""
    pass
