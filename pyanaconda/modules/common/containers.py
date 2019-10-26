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
from dasbus.container import DBusContainer
from pyanaconda.modules.common.constants.namespaces import STORAGE_NAMESPACE, ANACONDA_NAMESPACE, \
    PAYLOAD_NAMESPACE

TaskContainer = DBusContainer(
    namespace=ANACONDA_NAMESPACE,
    basename="Task"
)

DeviceTreeContainer = DBusContainer(
    namespace=STORAGE_NAMESPACE,
    basename="DeviceTree"
)

PartitioningContainer = DBusContainer(
    namespace=STORAGE_NAMESPACE,
    basename="Partitioning"
)

PayloadSourceContainer = DBusContainer(
    namespace=PAYLOAD_NAMESPACE,
    basename="Source"
)
