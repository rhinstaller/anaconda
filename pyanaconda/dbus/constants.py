#
# Anaconda DBUS constants
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

from pydbus.auto_names import auto_object_path

# main Anaconda DBUS namespace
ANACONDA_DBUS_NAMESPACE = "org.fedoraproject.Anaconda"

# DBUS namespace for modules
DBUS_MODULE_NAMESPACE = "{}.Modules".format(ANACONDA_DBUS_NAMESPACE)

# DBUS namespace for addons
DBUS_ADDON_NAMESPACE = "{}.Addons".format(ANACONDA_DBUS_NAMESPACE)

# BOSS
DBUS_BOSS_NAME = "{}.Boss".format(ANACONDA_DBUS_NAMESPACE)
DBUS_BOSS_PATH = auto_object_path(DBUS_BOSS_NAME)

DBUS_BOSS_INSTALLATION_NAME = "{}.Installation".format(DBUS_BOSS_NAME)
DBUS_BOSS_INSTALLATION_PATH = auto_object_path(DBUS_BOSS_INSTALLATION_NAME)

# Anaconda DBUS modules
MODULE_FOO_NAME = "{}.Foo".format(DBUS_MODULE_NAMESPACE)
MODULE_FOO_PATH = auto_object_path(MODULE_FOO_NAME)

MODULE_BAR_NAME = "{}.Bar".format(DBUS_MODULE_NAMESPACE)
MODULE_BAR_PATH = auto_object_path(MODULE_BAR_NAME)

# Addons (likely for testing purposes only)
ADDON_BAZ_NAME = "{}.Baz".format(DBUS_ADDON_NAMESPACE)
ADDON_BAZ_PATH = auto_object_path(ADDON_BAZ_NAME)

# list of all expected Anaconda services
ANACONDA_SERVICES = [MODULE_FOO_NAME,
                     MODULE_BAR_NAME]

# Task interface name
DBUS_TASK_NAME = "{}.Task".format(ANACONDA_DBUS_NAMESPACE)

# list of all expected Anaconda DBUS modules
ANACONDA_MODULES = [MODULE_FOO_PATH,
                    MODULE_BAR_PATH]

# status codes
DBUS_START_REPLY_SUCCESS = 1

# NOTE: There is no DBUS_START_REPLY_FAILURE or something similar,
#       as there is a separate field for error reporting.
#       For more information see the DBUS docs:
#       https://dbus.freedesktop.org/doc/dbus-specification.html#bus-messages-start-service-by-name




