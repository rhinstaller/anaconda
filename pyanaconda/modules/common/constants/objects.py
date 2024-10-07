#
# Known DBus objects.
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
from dasbus.identifier import DBusObjectIdentifier

from pyanaconda.modules.common.constants.namespaces import (
    DEVICE_TREE_NAMESPACE,
    NETWORK_NAMESPACE,
    PARTITIONING_NAMESPACE,
    RHSM_NAMESPACE,
    RUNTIME_NAMESPACE,
    SECURITY_NAMESPACE,
    STORAGE_NAMESPACE,
)

# Runtime objects

SCRIPTS = DBusObjectIdentifier(
    namespace=RUNTIME_NAMESPACE,
    basename="Scripts"
)

USER_INTERFACE = DBusObjectIdentifier(
    namespace=RUNTIME_NAMESPACE,
    basename="UserInterface"
)

# Storage objects.

BOOTLOADER = DBusObjectIdentifier(
    namespace=STORAGE_NAMESPACE,
    basename="Bootloader"
)

DASD = DBusObjectIdentifier(
    namespace=STORAGE_NAMESPACE,
    basename="DASD"
)

DEVICE_TREE = DBusObjectIdentifier(
    namespace=DEVICE_TREE_NAMESPACE
)

DISK_INITIALIZATION = DBusObjectIdentifier(
    namespace=STORAGE_NAMESPACE,
    basename="DiskInitialization"
)

DISK_SELECTION = DBusObjectIdentifier(
    namespace=STORAGE_NAMESPACE,
    basename="DiskSelection"
)

AUTO_PARTITIONING = DBusObjectIdentifier(
    namespace=PARTITIONING_NAMESPACE,
    basename="Automatic"
)

MANUAL_PARTITIONING = DBusObjectIdentifier(
    namespace=PARTITIONING_NAMESPACE,
    basename="Manual"
)

CUSTOM_PARTITIONING = DBusObjectIdentifier(
    namespace=PARTITIONING_NAMESPACE,
    basename="Custom"
)

INTERACTIVE_PARTITIONING = DBusObjectIdentifier(
    namespace=PARTITIONING_NAMESPACE,
    basename="Interactive"
)

BLIVET_PARTITIONING = DBusObjectIdentifier(
    namespace=PARTITIONING_NAMESPACE,
    basename="Blivet"
)

FCOE = DBusObjectIdentifier(
    namespace=STORAGE_NAMESPACE,
    basename="FCoE"
)

ISCSI = DBusObjectIdentifier(
    namespace=STORAGE_NAMESPACE,
    basename="iSCSI"
)

NVME = DBusObjectIdentifier(
    namespace=STORAGE_NAMESPACE,
    basename="NVMe"
)

SNAPSHOT = DBusObjectIdentifier(
    namespace=STORAGE_NAMESPACE,
    basename="Snapshot"
)

STORAGE_CHECKER = DBusObjectIdentifier(
    namespace=STORAGE_NAMESPACE,
    basename="Checker"
)

ZFCP = DBusObjectIdentifier(
    namespace=STORAGE_NAMESPACE,
    basename="zFCP"
)

# Network objects.

FIREWALL = DBusObjectIdentifier(
    namespace=NETWORK_NAMESPACE,
    basename="Firewall"
)

# System services

# Subscription objects.

RHSM_CONFIG = DBusObjectIdentifier(
    namespace=RHSM_NAMESPACE,
    basename="Config"
)

RHSM_REGISTER_SERVER = DBusObjectIdentifier(
    namespace=RHSM_NAMESPACE,
    basename="RegisterServer"
)

RHSM_REGISTER = DBusObjectIdentifier(
    namespace=RHSM_NAMESPACE,
    basename="Register"
)

RHSM_UNREGISTER = DBusObjectIdentifier(
    namespace=RHSM_NAMESPACE,
    basename="Unregister"
)

RHSM_SYSPURPOSE = DBusObjectIdentifier(
    namespace=RHSM_NAMESPACE,
    basename="Syspurpose"
)

# Security objects
CERTIFICATES = DBusObjectIdentifier(
    namespace=SECURITY_NAMESPACE,
    basename="Certificates"
)
