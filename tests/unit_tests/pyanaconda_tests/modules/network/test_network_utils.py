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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import unittest

import gi

gi.require_version("NM", "1.0")
from gi.repository import NM

from pyanaconda.modules.network.utils import (
    get_default_connection,
    is_ibft_configured_device,
    is_nbft_device,
)


class NetworkUtilsTestCase(unittest.TestCase):
    """Test the network utils."""

    def test_is_nbft_device(self):
        """Test the is_nbft_device function."""
        assert is_nbft_device("nbft0")
        assert is_nbft_device("nbft55")
        assert not is_nbft_device("")
        assert not is_nbft_device("eth0")
        assert not is_nbft_device("mynbft")

    def test_is_ibft_configured_device(self):
        """Test the is_ibft_configured_device function."""
        assert is_ibft_configured_device("ibft0")
        assert is_ibft_configured_device("ibft1")
        assert is_ibft_configured_device("ibft11")
        assert not is_ibft_configured_device("myibft0")
        assert not is_ibft_configured_device("ibft")
        assert not is_ibft_configured_device("ibftfirst")
        assert not is_ibft_configured_device("ibgt0")

    def test_get_default_ethernet_connection(self):
        """Test creating default Ethernet connection."""
        connection = get_default_connection("eth0", NM.DeviceType.ETHERNET)

        # Check connection settings
        s_con = connection.get_setting_connection()
        self.assertIsNotNone(s_con)
        self.assertEqual(s_con.props.id, "eth0")
        self.assertEqual(s_con.props.interface_name, "eth0")
        self.assertEqual(s_con.props.type, "802-3-ethernet")
        self.assertTrue(s_con.props.autoconnect)
        self.assertIsNotNone(s_con.props.uuid)

        # Check wired settings
        s_wired = connection.get_setting_wired()
        self.assertIsNotNone(s_wired)
