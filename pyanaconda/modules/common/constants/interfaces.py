#
# Known DBus interfaces.
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
from dasbus.identifier import DBusInterfaceIdentifier

from pyanaconda.modules.common.constants.namespaces import (
    ANACONDA_NAMESPACE,
    DEVICE_TREE_NAMESPACE,
    MODULES_NAMESPACE,
    PARTITIONING_NAMESPACE,
    PAYLOAD_NAMESPACE,
    SOURCE_NAMESPACE,
)

KICKSTART_MODULE = DBusInterfaceIdentifier(
    namespace=MODULES_NAMESPACE
)

PARTITIONING = DBusInterfaceIdentifier(
    namespace=PARTITIONING_NAMESPACE
)

TASK = DBusInterfaceIdentifier(
    namespace=ANACONDA_NAMESPACE,
    basename="Task"
)

TASK_CATEGORY = DBusInterfaceIdentifier(
    namespace=ANACONDA_NAMESPACE,
    basename="TaskCategory"
)

DEVICE_TREE_VIEWER = DBusInterfaceIdentifier(
    namespace=DEVICE_TREE_NAMESPACE,
    basename="Viewer"
)

DEVICE_TREE_HANDLER = DBusInterfaceIdentifier(
    namespace=DEVICE_TREE_NAMESPACE,
    basename="Handler"
)

DEVICE_TREE_RESIZABLE = DBusInterfaceIdentifier(
    namespace=DEVICE_TREE_NAMESPACE,
    basename="Resizable"
)

DEVICE_TREE_SCHEDULER = DBusInterfaceIdentifier(
    namespace=DEVICE_TREE_NAMESPACE,
    basename="Scheduler"
)

PAYLOAD = DBusInterfaceIdentifier(
    namespace=PAYLOAD_NAMESPACE
)

PAYLOAD_DNF = DBusInterfaceIdentifier(
    namespace=PAYLOAD_NAMESPACE,
    basename="DNF"
)

PAYLOAD_FLATPAK = DBusInterfaceIdentifier(
    namespace=PAYLOAD_NAMESPACE,
    basename="FLATPAK"
)

PAYLOAD_LIVE_IMAGE = DBusInterfaceIdentifier(
    namespace=PAYLOAD_NAMESPACE,
    basename="LiveImage"
)

PAYLOAD_LIVE_OS = DBusInterfaceIdentifier(
    namespace=PAYLOAD_NAMESPACE,
    basename="LiveOS"
)

PAYLOAD_RPM_OSTREE = DBusInterfaceIdentifier(
    namespace=PAYLOAD_NAMESPACE,
    basename="RPMOSTree"
)

PAYLOAD_SOURCE = DBusInterfaceIdentifier(
    namespace=SOURCE_NAMESPACE
)

PAYLOAD_SOURCE_LIVE_OS = DBusInterfaceIdentifier(
    namespace=SOURCE_NAMESPACE,
    basename="LiveOS"
)

PAYLOAD_SOURCE_LIVE_IMAGE = DBusInterfaceIdentifier(
    namespace=SOURCE_NAMESPACE,
    basename="LiveImage"
)

PAYLOAD_SOURCE_REPOSITORY = DBusInterfaceIdentifier(
    namespace=SOURCE_NAMESPACE,
    basename="Repository"
)

PAYLOAD_SOURCE_HMC = DBusInterfaceIdentifier(
    namespace=SOURCE_NAMESPACE,
    basename="HMC"
)

PAYLOAD_SOURCE_CDROM = DBusInterfaceIdentifier(
    namespace=SOURCE_NAMESPACE,
    basename="CDROM"
)

PAYLOAD_SOURCE_REPO_FILES = DBusInterfaceIdentifier(
    namespace=SOURCE_NAMESPACE,
    basename="RepoFiles"
)

PAYLOAD_SOURCE_REPO_PATH = DBusInterfaceIdentifier(
    namespace=SOURCE_NAMESPACE,
    basename="RepoPath"
)

PAYLOAD_SOURCE_CLOSEST_MIRROR = DBusInterfaceIdentifier(
    namespace=SOURCE_NAMESPACE,
    basename="ClosestMirror"
)

PAYLOAD_SOURCE_HARDDRIVE = DBusInterfaceIdentifier(
    namespace=SOURCE_NAMESPACE,
    basename="HDD"
)

PAYLOAD_SOURCE_CDN = DBusInterfaceIdentifier(
    namespace=SOURCE_NAMESPACE,
    basename="CDN"
)

PAYLOAD_SOURCE_RPM_OSTREE = DBusInterfaceIdentifier(
    namespace=SOURCE_NAMESPACE,
    basename="RPMOSTree"
)

PAYLOAD_SOURCE_RPM_OSTREE_CONTAINER = DBusInterfaceIdentifier(
    namespace=SOURCE_NAMESPACE,
    basename="RPMOSTreeContainer"
)

PAYLOAD_SOURCE_FLATPAK = DBusInterfaceIdentifier(
    namespace=SOURCE_NAMESPACE,
    basename="Flatpak"
)
