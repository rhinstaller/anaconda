#
# Copyright (C) 2013  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#

"""Module providing thread-safe and mainloop-safe DBus operations."""

import gi

gi.require_version("Gio", "2.0")

import os

from gi.repository import Gio

from pyanaconda.core.constants import DEFAULT_DBUS_TIMEOUT
from pyanaconda.core.glib import GError


class SafeDBusError(Exception):
    """Class for exceptions defined in this module."""

    pass


class DBusCallError(SafeDBusError):
    """Class for the errors related to calling methods over DBus."""

    pass


def get_new_session_connection():
    """
    Get a connection handle for the per-user-login-session message bus.

    !!! RUN THIS EARLY !!! like, before any other threads start. Connections to
    the session bus must be made with the effective UID of the login user,
    which in live installs is not the UID of anaconda. This means we need to
    call seteuid in this method, and doing that after threads have started will
    probably do something weird.

    Live installs use consolehelper to run as root, which sets the original
    UID in $USERHELPER_UID.

    :return: the session connection handle
    :rtype: Gio.DBusConnection
    :raise DBusCallError: if some DBus related error appears
    :raise OSError: if unable to set the effective UID
    """

    old_euid = None
    if "USERHELPER_UID" in os.environ:
        old_euid = os.geteuid()
        os.seteuid(int(os.environ["USERHELPER_UID"]))

    try:
        connection = Gio.DBusConnection.new_for_address_sync(
            Gio.dbus_address_get_for_bus_sync(Gio.BusType.SESSION, None),
            Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT |
            Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
            None, None)
    except GError as gerr:
        raise DBusCallError("Unable to connect to session bus: {}".format(gerr)) from gerr
    finally:
        if old_euid is not None:
            os.seteuid(old_euid)

    if connection.is_closed():
        raise DBusCallError("Connection is closed")

    return connection


def call_sync(service, obj_path, iface, method, args, connection):
    """
    Safely call a given method on a given object of a given service over DBus
    passing given arguments. If a connection is given, it is used, otherwise a
    new connection is established. Safely means that it is a synchronous,
    thread-safe call not using any main loop.

    :param service: DBus service to use
    :type service: str
    :param obj_path: object path of the object to call method on
    :type obj_path: str
    :param iface: interface to use
    :type iface: str
    :param method: name of the method to call
    :type method: str
    :param args: arguments to pass to the method
    :type args: GVariant
    :param connection: connection to use
    :type connection: Gio.DBusConnection
    :return: unpacked value returned by the method
    :rtype: tuple with elements that depend on the method
    :raise DBusCallError: if some DBus related error appears

    """
    if connection.is_closed():
        raise DBusCallError("Connection is closed")

    try:
        ret = connection.call_sync(service, obj_path, iface, method, args,
                                   None, Gio.DBusCallFlags.NONE,
                                   DEFAULT_DBUS_TIMEOUT, None)
    except GError as gerr:
        msg = "Failed to call %s method on %s with %s arguments: %s" % (method, obj_path,
                                                                        args, str(gerr))
        raise DBusCallError(msg) from gerr

    if ret is None:
        msg = "No return from %s method on %s with %s arguments" % (method, obj_path, args)
        raise DBusCallError(msg)

    return ret.unpack()
