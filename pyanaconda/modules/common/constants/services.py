#
# Known DBus services.
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
from dasbus.identifier import DBusServiceIdentifier

from pyanaconda.core.dbus import DBus, SessionBus, SystemBus
from pyanaconda.modules.common.constants.namespaces import (
    BOSS_NAMESPACE,
    LOCALIZATION_NAMESPACE,
    NETWORK_MANAGER_NAMESPACE,
    NETWORK_NAMESPACE,
    PAYLOADS_NAMESPACE,
    RHSM_NAMESPACE,
    RUNTIME_NAMESPACE,
    SECURITY_NAMESPACE,
    SERVICES_NAMESPACE,
    STORAGE_NAMESPACE,
    SUBSCRIPTION_NAMESPACE,
    TIMEZONE_NAMESPACE,
    USERS_NAMESPACE,
)

# Anaconda services.

BOSS = DBusServiceIdentifier(
    namespace=BOSS_NAMESPACE,
    message_bus=DBus
)

RUNTIME = DBusServiceIdentifier(
    namespace=RUNTIME_NAMESPACE,
    message_bus=DBus
)

TIMEZONE = DBusServiceIdentifier(
    namespace=TIMEZONE_NAMESPACE,
    message_bus=DBus
)

NETWORK = DBusServiceIdentifier(
    namespace=NETWORK_NAMESPACE,
    message_bus=DBus
)

LOCALIZATION = DBusServiceIdentifier(
    namespace=LOCALIZATION_NAMESPACE,
    message_bus=DBus
)

SECURITY = DBusServiceIdentifier(
    namespace=SECURITY_NAMESPACE,
    message_bus=DBus
)

USERS = DBusServiceIdentifier(
    namespace=USERS_NAMESPACE,
    message_bus=DBus
)

PAYLOADS = DBusServiceIdentifier(
    namespace=PAYLOADS_NAMESPACE,
    message_bus=DBus
)

STORAGE = DBusServiceIdentifier(
    namespace=STORAGE_NAMESPACE,
    message_bus=DBus
)

SERVICES = DBusServiceIdentifier(
    namespace=SERVICES_NAMESPACE,
    message_bus=DBus
)

SUBSCRIPTION = DBusServiceIdentifier(
    namespace=SUBSCRIPTION_NAMESPACE,
    message_bus=DBus
)

# System services.

HOSTNAME = DBusServiceIdentifier(
    namespace=("org", "freedesktop", "hostname"),
    service_version=1,
    object_version=1,
    interface_version=1,
    message_bus=SystemBus
)

LOCALED = DBusServiceIdentifier(
    namespace=("org", "freedesktop", "locale"),
    service_version=1,
    object_version=1,
    interface_version=1,
    message_bus=SystemBus
)

RHSM = DBusServiceIdentifier(
    namespace=RHSM_NAMESPACE,
    message_bus=SystemBus
)

NETWORK_MANAGER = DBusServiceIdentifier(
    namespace=NETWORK_MANAGER_NAMESPACE,
    message_bus=SystemBus
)

# Session services.

MUTTER_DISPLAY_CONFIG = DBusServiceIdentifier(
    namespace=("org", "gnome", "Mutter", "DisplayConfig"),
    message_bus=SessionBus
)
