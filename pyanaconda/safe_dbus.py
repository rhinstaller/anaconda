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
# Red Hat Author(s): Vratislav Podzimek <vpodzime@redhat.com>
#

"""Module providing thread-safe and mainloop-safe DBus operations."""

import os
from gi.repository import GLib, Gio
from pyanaconda.constants import DEFAULT_DBUS_TIMEOUT

DBUS_PROPS_IFACE = "org.freedesktop.DBus.Properties"

class SafeDBusError(Exception):
    """Class for exceptions defined in this module."""

    pass

class DBusCallError(SafeDBusError):
    """Class for the errors related to calling methods over DBus."""

    pass

class DBusPropertyError(DBusCallError):
    """Class for the errors related to getting property values over DBus."""

    pass

def get_new_system_connection():
    """Return a new connection to the system bus."""

    return Gio.DBusConnection.new_for_address_sync(
        Gio.dbus_address_get_for_bus_sync(Gio.BusType.SYSTEM, None),
        Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT|
        Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
        None, None)

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
            Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT|
            Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
            None, None)
    except GLib.GError as gerr:
        raise DBusCallError("Unable to connect to session bus: %s", gerr)
    finally:
        if old_euid is not None:
            os.seteuid(old_euid)

    if connection.is_closed():
        raise DBusCallError("Connection is closed")

    return connection

def call_sync(service, obj_path, iface, method, args,
                   connection=None):
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
    :param connection: connection to use (if None, a new connection is
                       established)
    :type connection: Gio.DBusConnection
    :return: unpacked value returned by the method
    :rtype: tuple with elements that depend on the method
    :raise DBusCallError: if some DBus related error appears

    """

    if not connection:
        try:
            connection = get_new_system_connection()
        except GLib.GError as gerr:
            raise DBusCallError("Unable to connect to system bus: %s", gerr)

    if connection.is_closed():
        raise DBusCallError("Connection is closed")

    try:
        ret = connection.call_sync(service, obj_path, iface, method, args,
                                   None, Gio.DBusCallFlags.NONE,
                                   DEFAULT_DBUS_TIMEOUT, None)
    except GLib.GError as gerr:
        msg = "Failed to call %s method on %s with %s arguments: %s" % \
                       (method, obj_path, args, gerr.message)
        raise DBusCallError(msg)

    if ret is None:
        msg = "No return from %s method on %s with %s arguments" % \
                       (method, obj_path, args)
        raise DBusCallError(msg)

    return ret.unpack()

def get_property_sync(service, obj_path, iface, prop_name,
                      connection=None):
    """
    Get value of a given property of a given object provided by a given service.

    :param service: DBus service to use
    :type service: str
    :param obj_path: object path
    :type obj_path: str
    :param iface: interface to use
    :type iface: str
    :param prop_name: name of the property
    :type prop_name: str
    :param connection: connection to use (if None, a new connection is
                       established)
    :type connection: Gio.DBusConnection
    :return: unpacked value of the property
    :rtype: tuple with elements that depend on the type of the property
    :raise DBusCallError: when the internal dbus_call_safe_sync invocation
                          raises an exception
    :raise DBusPropertyError: when the given object doesn't have the given
                              property

    """

    args = GLib.Variant('(ss)', (iface, prop_name))
    ret = call_sync(service, obj_path, DBUS_PROPS_IFACE, "Get", args,
                    connection)
    if ret is None:
        msg = "No value for the %s object's property %s" % (obj_path, prop_name)
        raise DBusPropertyError(msg)

    return ret
