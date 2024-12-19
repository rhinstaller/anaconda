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
"""The screensaver inhibition module.

The "screensaver" term includes the following effects, none of which we want during installation:
- locking the screen
- turning off the screen
- suspending the system

See also the origin bz: https://bugzilla.redhat.com/show_bug.cgi?id=928825

We are using the freedesktop D-Bus api for inhibiting the screensaver:
    https://people.freedesktop.org/~hadess/idle-inhibition-spec/re01.html

Note this does NOT use the systemd / logind API with similar name and capability!

The D-Bus api lives on the session bus. Connections to the session bus must be made with the
effective UID of the login user, which in live installs is not the UID of anaconda. This means
we need to call seteuid while creating the proxy and making calls on the bus.

Additionally, at the time of writing, creating the proxy actually starts the session bus daemon
and so creates the bus. Conversely, when the proxy stops existing, the bus goes down.

The inhibition is in effect only if all of these conditions are met:
- The process called Inhibit on the session bus for the correct user.
- The process exists.
- The session bus exists.
- The process did not call UnInhibit on the session bus with the right cookie.

Altogether this means that once the proxy is correctly created, we call Inhibit, and then
the proxy object must exist as long as we want the inhibition to be in effect.
"""
import os

from dasbus.connection import SessionMessageBus
from dasbus.error import DBusError
from dasbus.identifier import DBusServiceIdentifier

from pyanaconda.anaconda_loggers import get_module_logger

log = get_module_logger(__name__)

__all__ = ["inhibit_screensaver", "uninhibit_screensaver"]


session_proxy = None
inhibit_id = None


class SetEuidFromPkexec():
    """Context manager to temporarily set euid from env. variable set by consolehelper.

    Live installs use pkexec to run as root, which sets the original UID in $PKEXEC_UID.
    """
    def __init__(self):
        self.old_euid = None

    def __enter__(self):
        if "PKEXEC_UID" in os.environ:
            self.old_euid = os.geteuid()
            new_euid = int(os.environ["PKEXEC_UID"])
            os.seteuid(new_euid)
        return self

    def __exit__(self, _exc_type, _exc_value, _exc_traceback):
        if self.old_euid is not None:
            os.seteuid(self.old_euid)
            self.old_euid = None


def inhibit_screensaver():
    """Inhibit the "screensaver" idle timer."""
    log.info("Inhibiting screensaver.")
    global session_proxy
    global inhibit_id
    try:
        with SetEuidFromPkexec():
            SCREENSAVER = DBusServiceIdentifier(
                namespace=("org", "freedesktop", "ScreenSaver"),
                message_bus=SessionMessageBus()
            )
            session_proxy = SCREENSAVER.get_proxy()
            inhibit_id = session_proxy.Inhibit("anaconda", "Installing")
    except DBusError as e:
        log.warning("Unable to inhibit the screensaver: %s", e)


def uninhibit_screensaver():
    """Re-enable the "screensaver" idle timer."""
    if session_proxy is None or inhibit_id is None:
        return
    log.info("Un-inhibiting screensaver.")
    try:
        with SetEuidFromPkexec():
            session_proxy.UnInhibit(inhibit_id)
    except (DBusError, KeyError) as e:
        log.warning("Unable to uninhibit the screensaver: %s", e)
