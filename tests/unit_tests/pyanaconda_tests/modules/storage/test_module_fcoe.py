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
import unittest
import pytest

from unittest.mock import patch

from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.modules.common.errors.configuration import StorageDiscoveryError
from pyanaconda.modules.storage.fcoe import FCOEModule
from pyanaconda.modules.storage.fcoe.discover import FCOEDiscoverTask
from pyanaconda.modules.storage.fcoe.fcoe_interface import FCOEInterface
from tests.unit_tests.pyanaconda_tests import patch_dbus_publish_object, check_task_creation


class FCOEInterfaceTestCase(unittest.TestCase):
    """Test DBus interface of the FCoE module."""

    def setUp(self):
        """Set up the module."""
        self.fcoe_module = FCOEModule()
        self.fcoe_interface = FCOEInterface(self.fcoe_module)

    @patch("pyanaconda.modules.storage.fcoe.fcoe.has_fcoe", return_value=True)
    def test_is_supported(self, is_supported):
        assert self.fcoe_interface.IsSupported() is True

    def test_get_nics(self):
        """Test the get nics method."""
        assert self.fcoe_interface.GetNics() == list()

    def test_get_dracut_arguments(self):
        """Test the get dracut arguments method."""
        assert self.fcoe_interface.GetDracutArguments("eth0") == list()

    @patch_dbus_publish_object
    def test_discover_with_task(self, publisher):
        """Test the discover task."""
        task_path = self.fcoe_interface.DiscoverWithTask(
            "eth0",  # nic
            False,  # dcb
            True  # auto_vlan
        )

        obj = check_task_creation(task_path, publisher, FCOEDiscoverTask)

        assert obj.implementation._nic == "eth0"
        assert obj.implementation._dcb is False
        assert obj.implementation._auto_vlan is True

    @patch('pyanaconda.modules.storage.fcoe.fcoe.fcoe')
    def test_write_configuration(self, fcoe):
        """Test WriteConfiguration."""
        self.fcoe_interface.WriteConfiguration()
        fcoe.write.assert_called_once_with(conf.target.system_root)


class FCOETasksTestCase(unittest.TestCase):
    """Test FCoE tasks."""

    @patch('pyanaconda.modules.storage.fcoe.discover.fcoe')
    def test_discovery_fails(self, fcoe):
        """Test the failing discovery task."""
        fcoe.add_san.return_value = "Fake error message"

        with pytest.raises(StorageDiscoveryError) as cm:
            FCOEDiscoverTask(nic="eth0", dcb=False, auto_vlan=True).run()

        assert str(cm.value) == "Fake error message"

    @patch('pyanaconda.modules.storage.fcoe.discover.fcoe')
    def test_discovery(self, fcoe):
        """Test the discovery task."""
        fcoe.add_san.return_value = ""

        FCOEDiscoverTask(nic="eth0", dcb=False, auto_vlan=True).run()

        fcoe.add_san.assert_called_once_with("eth0", False, True)
        fcoe.added_nics.append.assert_called_once_with("eth0")
