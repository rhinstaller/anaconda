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
from pyanaconda.dbus.identifier import DBusInterfaceIdentifier
from pyanaconda.modules.common.constants.namespaces import ANACONDA_NAMESPACE, BOSS_NAMESPACE, \
    MODULES_NAMESPACE


KICKSTART_MODULE = DBusInterfaceIdentifier(
    namespace=MODULES_NAMESPACE
)

BOSS_ANACONDA = DBusInterfaceIdentifier(
    namespace=BOSS_NAMESPACE,
    basename="Anaconda"
)

TASK = DBusInterfaceIdentifier(
    namespace=ANACONDA_NAMESPACE,
    basename="Task"
)
