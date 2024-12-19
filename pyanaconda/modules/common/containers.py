#
# DBus containers
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
from dasbus.server.container import DBusContainer

from pyanaconda.core.dbus import DBus
from pyanaconda.modules.common.constants.namespaces import (
    ANACONDA_NAMESPACE,
    DEVICE_TREE_NAMESPACE,
    PARTITIONING_NAMESPACE,
    PAYLOAD_NAMESPACE,
    SOURCE_NAMESPACE,
)

TaskContainer = DBusContainer(
    namespace=ANACONDA_NAMESPACE,
    basename="Task",
    message_bus=DBus
)

DeviceTreeContainer = DBusContainer(
    namespace=DEVICE_TREE_NAMESPACE,
    message_bus=DBus
)

PartitioningContainer = DBusContainer(
    namespace=PARTITIONING_NAMESPACE,
    message_bus=DBus
)

PayloadContainer = DBusContainer(
    namespace=PAYLOAD_NAMESPACE,
    message_bus=DBus
)

PayloadSourceContainer = DBusContainer(
    namespace=SOURCE_NAMESPACE,
    message_bus=DBus
)
