#
# Copyright (C) 2019  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Vendula Poncova <vponcova@redhat.com>
#
import tempfile
import unittest
import pytest
from unittest.mock import patch

from pyanaconda.core.dbus import AnacondaMessageBus, DefaultMessageBus
from dasbus.constants import DBUS_STARTER_ADDRESS
from pyanaconda.core.constants import DBUS_ANACONDA_SESSION_ADDRESS

import gi
gi.require_version("Gio", "2.0")
from gi.repository import Gio


class AnacondaDBusConnectionTestCase(unittest.TestCase):
    """Test Anaconda DBus connection."""

    def _check_addressed_connection(self, message_bus, getter, address):
        assert message_bus.connection is not None
        assert message_bus.address == address
        getter.assert_called_once_with(
            address,
            (
                Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT |
                Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION
            ),
            None,
            None
        )

    def _check_anaconda_connection(self, message_bus, getter):
        with pytest.raises(ConnectionError):
            self._check_addressed_connection(message_bus, getter, "ADDRESS")

        with tempfile.NamedTemporaryFile("w") as f:
            f.write("ADDRESS")
            f.flush()

            with patch("pyanaconda.core.dbus.ANACONDA_BUS_ADDR_FILE", f.name):
                self._check_addressed_connection(message_bus, getter, "ADDRESS")

        with patch.dict("os.environ") as environment:
            environment[DBUS_ANACONDA_SESSION_ADDRESS] = "ADDRESS"
            self._check_addressed_connection(message_bus, getter, "ADDRESS")

    @patch("dasbus.connection.Gio.DBusConnection.new_for_address_sync")
    def test_anaconda_bus(self, getter):
        """Test the anaconda bus."""
        message_bus = AnacondaMessageBus()
        self._check_anaconda_connection(message_bus, getter)

    @patch("dasbus.connection.Gio.DBusConnection.new_for_address_sync")
    def test_default_bus(self, getter):
        """Test the default bus."""
        message_bus = DefaultMessageBus()

        with patch.dict("os.environ") as environment:
            environment[DBUS_STARTER_ADDRESS] = "ADDRESS"
            self._check_addressed_connection(message_bus, getter, "ADDRESS")

        self._check_anaconda_connection(message_bus, getter)
