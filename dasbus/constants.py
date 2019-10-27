#
# DBus constants
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

# Status codes.
DBUS_START_REPLY_SUCCESS = 1

# No flags are set.
DBUS_FLAG_NONE = 0

# System environment variable holding the DBus session address.
DBUS_STARTER_ADDRESS = "DBUS_STARTER_ADDRESS"

# Return values of org.freedesktop.DBus.RequestName.
DBUS_REQUEST_NAME_REPLY_PRIMARY_OWNER = 1
DBUS_REQUEST_NAME_REPLY_IN_QUEUE = 2
DBUS_REQUEST_NAME_REPLY_EXISTS = 3
DBUS_REQUEST_NAME_REPLY_ALREADY_OWNER = 4

# Flags of org.freedesktop.DBus.RequestName.
DBUS_NAME_FLAG_ALLOW_REPLACEMENT = 0x1
DBUS_NAME_FLAG_REPLACE_EXISTING = 0x2
DBUS_NAME_FLAG_DO_NOT_QUEUE = 0x3
