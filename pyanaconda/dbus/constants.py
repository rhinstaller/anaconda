#
# DBus constants.
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

# no flags are set
DBUS_FLAG_NONE = 0

# status codes
DBUS_START_REPLY_SUCCESS = 1

# NOTE: There is no DBUS_START_REPLY_FAILURE or something similar,
#       as there is a separate field for error reporting.
#       For more information see the DBUS docs:
#       https://dbus.freedesktop.org/doc/dbus-specification.html#bus-messages-start-service-by-name
