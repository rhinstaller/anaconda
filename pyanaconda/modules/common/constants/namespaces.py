#
# DBus namespaces, where a namespace is just a tuple of strings.
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

ANACONDA_NAMESPACE = (
    "org", "fedoraproject", "Anaconda"
)

MODULES_NAMESPACE = (
    *ANACONDA_NAMESPACE,
    "Modules"
)

ADDONS_NAMESPACE = (
    *ANACONDA_NAMESPACE,
    "Addons"
)

BOSS_NAMESPACE = (
    *ANACONDA_NAMESPACE,
    "Boss"
)

RUNTIME_NAMESPACE = (
    *MODULES_NAMESPACE,
    "Runtime"
)

TIMEZONE_NAMESPACE = (
    *MODULES_NAMESPACE,
    "Timezone"
)

NETWORK_NAMESPACE = (
    *MODULES_NAMESPACE,
    "Network",
)

LOCALIZATION_NAMESPACE = (
    *MODULES_NAMESPACE,
    "Localization",
)

SECURITY_NAMESPACE = (
    *MODULES_NAMESPACE,
    "Security"
)

USERS_NAMESPACE = (
    *MODULES_NAMESPACE,
    "Users"
)

STORAGE_NAMESPACE = (
    *MODULES_NAMESPACE,
    "Storage"
)

DEVICE_TREE_NAMESPACE = (
    *STORAGE_NAMESPACE,
    "DeviceTree"
)

PARTITIONING_NAMESPACE = (
    *STORAGE_NAMESPACE,
    "Partitioning"
)

SERVICES_NAMESPACE = (
    *MODULES_NAMESPACE,
    "Services"
)

SUBSCRIPTION_NAMESPACE = (
    *MODULES_NAMESPACE,
    "Subscription"
)

PAYLOADS_NAMESPACE = (
    *MODULES_NAMESPACE,
    "Payloads"
)

PAYLOAD_NAMESPACE = (
    *PAYLOADS_NAMESPACE,
    "Payload"
)

SOURCE_NAMESPACE = (
    *PAYLOADS_NAMESPACE,
    "Source"
)

# System service namespaces

RHSM_NAMESPACE = (
    "com", "redhat", "RHSM1"
)

NETWORK_MANAGER_NAMESPACE = (
    "org", "freedesktop", "NetworkManager"
)
