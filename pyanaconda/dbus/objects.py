#
# Known DBus objects and services.
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
from pyanaconda.dbus.namespace import DBusNamespace, DBusServiceIdentifier, \
    DBusObjectIdentifier, DBusInterfaceIdentifier

ANACONDA_NAMESPACE = DBusNamespace(
    "org", "fedoraproject", "Anaconda"
)

KICKSTART_MODULE = DBusInterfaceIdentifier(
    "Modules",
    namespace=ANACONDA_NAMESPACE
)

KICKSTART_ADDON = DBusNamespace(
    "Addons",
    namespace=ANACONDA_NAMESPACE
)

BOSS = DBusServiceIdentifier(
    "Boss",
    namespace=ANACONDA_NAMESPACE
)

BOSS_INSTALLATION = DBusObjectIdentifier(
    "Installation",
    namespace=BOSS
)

BOSS_ANACONDA = DBusInterfaceIdentifier(
    "Anaconda",
    namespace=BOSS
)

FOO = DBusServiceIdentifier(
    "Foo",
    namespace=KICKSTART_MODULE
)

BAR = DBusServiceIdentifier(
    "Bar",
    namespace=KICKSTART_MODULE
)

TIMEZONE = DBusServiceIdentifier(
    "Timezone",
    namespace=KICKSTART_MODULE
)

BAZ = DBusServiceIdentifier(
    "Baz",
    namespace=KICKSTART_ADDON
)

TASK = DBusInterfaceIdentifier(
    "Task",
    namespace=ANACONDA_NAMESPACE
)

# List of all kickstart modules.
ALL_KICKSTART_MODULES = [
    FOO,
    BAR,
    TIMEZONE
]
