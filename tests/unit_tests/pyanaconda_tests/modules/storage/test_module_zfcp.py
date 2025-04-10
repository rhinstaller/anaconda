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
from pyanaconda.modules.storage.zfcp import ZFCPModule
from pyanaconda.modules.storage.zfcp.discover import ZFCPDiscoverTask
from pyanaconda.modules.storage.zfcp.zfcp_interface import ZFCPInterface
from tests.unit_tests.pyanaconda_tests import patch_dbus_publish_object, check_task_creation


class ZFCPInterfaceTestCase(unittest.TestCase):
    """Test DBus interface of the zFCP module."""

    def setUp(self):
        """Set up the module."""
        self.zfcp_module = ZFCPModule()
        self.zfcp_interface = ZFCPInterface(self.zfcp_module)

    @patch("pyanaconda.modules.storage.dasd.dasd.arch.is_s390", return_value=True)
    def test_is_supported(self, is_supported):
        assert self.zfcp_interface.IsSupported() is True

    @patch_dbus_publish_object
    def test_discover_with_task(self, publisher):
        """Test the discover task."""
        task_path = self.zfcp_interface.DiscoverWithTask(
            "0.0.fc00",
            "0x5105074308c212e9",
            "0x401040a000000000"
        )

        obj = check_task_creation(task_path, publisher, ZFCPDiscoverTask)

        assert obj.implementation._device_number == "0.0.fc00"
        assert obj.implementation._wwpn == "0x5105074308c212e9"
        assert obj.implementation._lun == "0x401040a000000000"

    @patch('pyanaconda.modules.storage.zfcp.zfcp.zfcp')
    @patch("pyanaconda.modules.storage.zfcp.zfcp.arch.is_s390", return_value=True)
    def test_write_configuration(self, arch, zfcp):
        """Test WriteConfiguration."""
        self.zfcp_interface.WriteConfiguration()
        zfcp.write.assert_called_once_with(conf.target.system_root)


class ZFCPTasksTestCase(unittest.TestCase):
    """Test zFCP tasks."""

    def test_discovery_missing_values(self):
        """Test the discovery task with missing values."""

        with pytest.raises(StorageDiscoveryError) as cm:
            ZFCPDiscoverTask("", "", "").run()

        assert str(cm.value) == "Incorrect format of the given device number."

        with pytest.raises(StorageDiscoveryError) as cm:
            ZFCPDiscoverTask("0.0.fc00", "", "0x401040a000000000").run()

        msg = "Only device number or device number with WWPN and LUN are allowed."
        assert str(cm.value) == msg

        with pytest.raises(StorageDiscoveryError) as cm:
            ZFCPDiscoverTask("0.0.fc00", "0x5105074308c212e9", "").run()

        msg = "Only device number or device number with WWPN and LUN are allowed."
        assert str(cm.value) == msg

    def test_discovery_invalid_values(self):
        """Test the discovery task with invalid values."""

        with pytest.raises(StorageDiscoveryError) as cm:
            ZFCPDiscoverTask("1+2", "", "").run()

        assert str(cm.value) == "Incorrect format of the given device number."

        with pytest.raises(StorageDiscoveryError) as cm:
            ZFCPDiscoverTask("0.0.fc00", "1+2", "").run()

        assert str(cm.value) == "Incorrect format of the given WWPN number."

        with pytest.raises(StorageDiscoveryError) as cm:
            ZFCPDiscoverTask("0.0.fc00", "0x5105074308c212e9", "1+2").run()

        assert str(cm.value) == "Incorrect format of the given LUN number."

    @patch('pyanaconda.modules.storage.zfcp.discover.zfcp')
    @patch('pyanaconda.modules.storage.zfcp.discover.blockdev')
    def test_discovery(self, blockdev, zfcp):
        """Test the discovery task."""
        ZFCPDiscoverTask("0.0.fc00", "0x5105074308c212e9", "0x401040a000000000").run()

        blockdev.s390.sanitize_dev_input.assert_called_once_with("0.0.fc00")
        blockdev.s390.zfcp_sanitize_wwpn_input.assert_called_once_with("0x5105074308c212e9")
        blockdev.s390.zfcp_sanitize_lun_input.assert_called_once_with("0x401040a000000000")

        sanitized_dev = blockdev.s390.sanitize_dev_input.return_value
        sanitized_wwpn = blockdev.s390.zfcp_sanitize_wwpn_input.return_value
        sanitized_lun = blockdev.s390.zfcp_sanitize_lun_input.return_value

        zfcp.add_fcp.assert_called_once_with(sanitized_dev, sanitized_wwpn, sanitized_lun)

    @patch('pyanaconda.modules.storage.zfcp.discover.zfcp')
    @patch('pyanaconda.modules.storage.zfcp.discover.blockdev')
    def test_discovery_npiv(self, blockdev, zfcp):
        """Test the discovery task for an NPIV enabled zFCP."""
        ZFCPDiscoverTask("0.0.fc00", "", "").run()

        blockdev.s390.sanitize_dev_input.assert_called_once_with("0.0.fc00")
        blockdev.s390.zfcp_sanitize_wwpn_input.assert_not_called()
        blockdev.s390.zfcp_sanitize_lun_input.assert_not_called()

        sanitized_dev = blockdev.s390.sanitize_dev_input.return_value

        zfcp.add_fcp.assert_called_once_with(sanitized_dev, "", "")
