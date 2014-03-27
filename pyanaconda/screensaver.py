#
# screensaver.py - Screensaver management methods and data
#
# Copyright (C) 2014 Red Hat, Inc.  All rights reserved.
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
# Author(s): David Shea <dshea@redhat.com>
#

from pyanaconda import safe_dbus
from gi.repository import GLib

import logging
log = logging.getLogger("anaconda")

SCREENSAVER_SERVICE = "org.freedesktop.ScreenSaver"
SCREENSAVER_PATH    = "/org/freedesktop/ScreenSaver"
SCREENSAVER_IFACE   = "org.freedesktop.ScreenSaver"

SCREENSAVER_INHIBIT_METHOD   = "Inhibit"
SCREENSAVER_UNINHIBIT_METHOD = "UnInhibit"

SCREENSAVER_APPLICATION = "anaconda"
SCREENSAVER_REASON      = "Installing"

def inhibit_screensaver(connection):
    """
    Inhibit the screensaver idle timer.

    :param connection: A handle for the session message bus
    :type connection: Gio.DBusConnection
    :return: The inhibit ID or None
    :rtype: int or None
    """

    try:
        inhibit_id = safe_dbus.call_sync(SCREENSAVER_SERVICE, SCREENSAVER_PATH, SCREENSAVER_IFACE,
                SCREENSAVER_INHIBIT_METHOD, GLib.Variant('(ss)',
                    (SCREENSAVER_APPLICATION, SCREENSAVER_REASON)),
                connection)
        return inhibit_id[0]
    except safe_dbus.DBusCallError as e:
        log.info("Unable to inhibit the screensaver: %s", e)

    return None

def uninhibit_screensaver(connection, inhibit_id):
    """
    Re-enable the screensaver idle timer.

    :param connection: A handle for the session message bus
    :type connection: Gio.DBusConnection
    :param inhibit_id: The ID returned by the inhibit method
    :type inhibit_id: int
    """

    try:
        safe_dbus.call_sync(SCREENSAVER_SERVICE, SCREENSAVER_PATH, SCREENSAVER_IFACE,
                SCREENSAVER_UNINHIBIT_METHOD, GLib.Variant('(u)', (inhibit_id,)), connection)
    except safe_dbus.DBusCallError as e:
        log.info("Unable to uninhibit the screensaver: %s", e)
