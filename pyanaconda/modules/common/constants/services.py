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
from pyanaconda.dbus import SystemBus
from pyanaconda.dbus.identifier import DBusServiceIdentifier
from pyanaconda.modules.common.constants.namespaces import BOSS_NAMESPACE, TIMEZONE_NAMESPACE, \
    NETWORK_NAMESPACE, LOCALIZATION_NAMESPACE, SECURITY_NAMESPACE, USERS_NAMESPACE, BAZ_NAMESPACE, \
    PAYLOAD_NAMESPACE, STORAGE_NAMESPACE, SERVICES_NAMESPACE

# Anaconda services.

BOSS = DBusServiceIdentifier(
    namespace=BOSS_NAMESPACE
)

BAZ = DBusServiceIdentifier(
    namespace=BAZ_NAMESPACE
)

TIMEZONE = DBusServiceIdentifier(
    namespace=TIMEZONE_NAMESPACE
)

NETWORK = DBusServiceIdentifier(
    namespace=NETWORK_NAMESPACE
)

LOCALIZATION = DBusServiceIdentifier(
    namespace=LOCALIZATION_NAMESPACE
)

SECURITY = DBusServiceIdentifier(
    namespace=SECURITY_NAMESPACE
)

USERS = DBusServiceIdentifier(
    namespace=USERS_NAMESPACE
)

PAYLOAD = DBusServiceIdentifier(
    namespace=PAYLOAD_NAMESPACE
)

STORAGE = DBusServiceIdentifier(
    namespace=STORAGE_NAMESPACE
)

SERVICES = DBusServiceIdentifier(
    namespace=SERVICES_NAMESPACE
)

# System services.

HOSTNAME = DBusServiceIdentifier(
    namespace=("org", "freedesktop", "hostname"),
    service_version=1,
    object_version=1,
    interface_version=1,
    message_bus=SystemBus
)

# Other constants.

ALL_KICKSTART_MODULES = [
    TIMEZONE,
    NETWORK,
    LOCALIZATION,
    SECURITY,
    USERS,
    PAYLOAD,
    STORAGE,
    SERVICES,
]
