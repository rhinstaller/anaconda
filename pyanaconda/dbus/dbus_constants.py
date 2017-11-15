#
# dbus/constants.py: Anaconda DBUS constants
#
# Copyright (C) 2017  Red Hat, Inc.  All rights reserved.
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

# main Anaconda DBUS namespace
ANACONDA_DBUS_NAMESPACE = "org.fedoraproject.Anaconda"

# DBUS namespace for modules
DBUS_MODULE_NAMESPACE = "{}.Modules".format(ANACONDA_DBUS_NAMESPACE)

# DBUS namespace for addons
DBUS_ADDON_NAMESPACE = "{}.Addons".format(ANACONDA_DBUS_NAMESPACE)

# BOSS
DBUS_BOSS_NAME = "{}.Boss".format(ANACONDA_DBUS_NAMESPACE)

# Anaconda DBUS modules
MODULE_FOO = "{}.Foo".format(DBUS_MODULE_NAMESPACE)
MODULE_BAR = "{}.Bar".format(DBUS_MODULE_NAMESPACE)

# Addons (likely for testing purposes only)
ADDON_BAZ = "{}.Baz".format(DBUS_ADDON_NAMESPACE)

# list of all expected Anaconda DBUS modules
ANACONDA_MODULES = [MODULE_FOO, MODULE_BAR]

# status codes
DBUS_START_REPLY_SUCCESS = 1

# NOTE: There is no DBUS_START_REPLY_FAILURE or something similar,
#       as there is a separate field for error reporting.
#       For more information see the DBUS docs:
#       https://dbus.freedesktop.org/doc/dbus-specification.html#bus-messages-start-service-by-name




