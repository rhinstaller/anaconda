#
# Copyright (C) 2024  Red Hat, Inc.
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
import os
from unittest import TestCase
from unittest.mock import patch

from pyanaconda.display import start_user_systemd


class DisplayUtilsTestCase(TestCase):
    """Test the display utils."""

    @patch.dict("os.environ", clear=True)
    @patch("pyanaconda.display.WatchProcesses")
    @patch("pyanaconda.display.conf")
    @patch("pyanaconda.display.util")
    def test_start_user_systemd(self, util_mock, conf_mock, watch_mock):
        """Start a user instance of systemd on a boot.iso."""
        # Don't start systemd --user if this is not a boot.iso.
        conf_mock.system.can_start_user_systemd = False
        start_user_systemd()

        util_mock.startProgram.assert_not_called()
        util_mock.reset_mock()

        # Start systemd --user on a boot.iso.
        # pylint: disable=environment-modify
        os.environ["XDG_RUNTIME_DIR"] = "/my/xdg/path"
        conf_mock.system.can_start_user_systemd = True
        util_mock.startProgram.return_value = 100
        start_user_systemd()

        util_mock.startProgram.assert_called_once_with(
            ["/usr/lib/systemd/systemd", "--user"]
        )
        watch_mock.watch_process.assert_called_once_with(
            100, "systemd"
        )
        assert os.environ["DBUS_SESSION_BUS_ADDRESS"] == \
            "unix:path=/my/xdg/path/bus"
