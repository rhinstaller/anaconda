#
# Copyright (C) 2018  Red Hat, Inc.
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
# Red Hat Author(s): Radek Vykydal <rvykydal@redhat.com>
#
import gi
gi.require_version("BlockDev", "2.0")
from gi.repository import BlockDev as blockdev

import unittest
from textwrap import dedent
from unittest.mock import patch, Mock

from tests.nosetests.pyanaconda_tests import patch_dbus_publish_object, check_task_creation

from pyanaconda.modules.common.errors.configuration import StorageConfigurationError
from pyanaconda.modules.storage.nvdimm import NVDIMMModule
from pyanaconda.modules.storage.nvdimm.nvdimm_interface import NVDIMMInterface
from pyanaconda.modules.storage.nvdimm.reconfigure import NVDIMMReconfigureTask
from pyanaconda.modules.storage.storage import StorageService
from pykickstart.constants import NVDIMM_MODE_SECTOR, NVDIMM_ACTION_RECONFIGURE


class NVDIMMInterfaceTestCase(unittest.TestCase):
    """Test DBus interface of the NVDIMM module."""

    def setUp(self):
        """Set up the module."""
        self.nvdimm_module = NVDIMMModule()
        self.nvdimm_interface = NVDIMMInterface(self.nvdimm_module)

    def is_supported_test(self):
        self.assertEqual(self.nvdimm_interface.IsSupported(), True)

    def get_devices_to_ignore_test(self):
        """Test GetDevicesToIgnore."""
        self.assertEqual(self.nvdimm_interface.GetDevicesToIgnore(), [])

    def set_namespaces_to_use_test(self):
        """Test SetNamespacesToUse."""
        self.nvdimm_interface.SetNamespacesToUse(["namespace0.0", "namespace1.0"])

    @patch_dbus_publish_object
    def reconfigure_with_task_test(self, publisher):
        """Test ReconfigureWithTask."""
        task_path = self.nvdimm_interface.ReconfigureWithTask("namespace0.0", "sector", 512)

        obj = check_task_creation(self, task_path, publisher, NVDIMMReconfigureTask)

        self.assertEqual(obj.implementation._namespace, "namespace0.0")
        self.assertEqual(obj.implementation._mode, "sector")
        self.assertEqual(obj.implementation._sector_size, 512)

        self.assertIsNone(self.nvdimm_module.find_action("namespace0.0"))
        obj.implementation.succeeded_signal.emit()

        action = self.nvdimm_module.find_action("namespace0.0")
        self.assertEqual(action.action, NVDIMM_ACTION_RECONFIGURE)
        self.assertEqual(action.namespace, "namespace0.0")
        self.assertEqual(action.mode, "sector")
        self.assertEqual(action.sectorsize, 512)


class NVDIMMTasksTestCase(unittest.TestCase):
    """Test NVDIMM tasks."""

    def failed_reconfiguration_test(self):
        """Test the reconfiguration test."""
        with self.assertRaises(StorageConfigurationError):
            NVDIMMReconfigureTask("namespace0.0", "sector", 512).run()

    @patch("pyanaconda.modules.storage.nvdimm.reconfigure.nvdimm")
    def reconfiguration_test(self, nvdimm):
        """Test the reconfiguration test."""
        NVDIMMReconfigureTask(
            "namespace0.0", "sector", sector_size=512
        ).run()

        nvdimm.reconfigure_namespace.assert_called_once_with(
            "namespace0.0", "sector", sector_size=512
        )


class NVDIMMKickstartTestCase(unittest.TestCase):
    """Test updating of nvdimm command from UI.

    The update is done:
    - always by disk selection in UI.
    - optionally by reconfiguring NVDIMM in UI.
    """

    def setUp(self):
        self.storage_module = StorageService()
        self.nvdimm_module = self.storage_module._nvdimm_module
        self.nvdimm_interface = NVDIMMInterface(self.nvdimm_module)

    def _read(self, input_ks):
        """Read the kickstart string."""
        with patch("pyanaconda.modules.storage.kickstart.nvdimm") as nvdimm:
            # Fake the existence of the namespaces.
            nvdimm.namespaces = ["namespace0.0", "namespace1.0"]

            # Parse the kickstart now.
            self.storage_module.read_kickstart(input_ks)

    def _use(self, namespaces):
        """Represents update for NVDIMM disks selected in UI."""
        self.nvdimm_module.set_namespaces_to_use(
            namespaces=namespaces
        )

    def _reconfigure(self, namespace, sector_size):
        """Represents update for NVDIMM disk reconfigured in UI."""
        self.nvdimm_module.update_action(
            namespace=namespace,
            mode=NVDIMM_MODE_SECTOR,
            sector_size=sector_size
        )

    def _check(self, expected_ks):
        """Check the generated kickstart."""
        self.assertEqual(
            self.storage_module.generate_kickstart().strip(),
            dedent(expected_ks).strip()
        )

    def _check_ignored(self, expected_devices):
        """Check the ignored devices."""
        with patch("pyanaconda.modules.storage.nvdimm.nvdimm.nvdimm") as nvdimm:
            nvdimm.namespaces = {
                "namespace0.0": Mock(blockdev="pmem0", mode=blockdev.NVDIMMNamespaceMode.SECTOR),
                "namespace1.0": Mock(blockdev="pmem1", mode=blockdev.NVDIMMNamespaceMode.SECTOR),
                "namespace2.0": Mock(blockdev="pmem2", mode=blockdev.NVDIMMNamespaceMode.MEMORY),
                "namespace3.0": Mock(blockdev=None, mode=blockdev.NVDIMMNamespaceMode.DEVDAX),
            }

            ignored_devices = self.nvdimm_module.get_devices_to_ignore()
            self.assertEqual(sorted(ignored_devices), expected_devices)

    # Test setting use from UI

    def ksuse_use_test(self):
        """Test updating of nvdimm commands based on device selection in UI."""
        input_ks = """
        nvdimm use --namespace=namespace0.0
        """
        expected_ks = """
        # NVDIMM devices setup
        nvdimm use --namespace=namespace0.0
        """
        self._read(input_ks)
        self._check_ignored(["pmem1", "pmem2"])
        self._use(["namespace0.0"])
        self._check(expected_ks)

    def ksuse_use2_test(self):
        """Test updating of nvdimm commands based on device selection in UI."""
        input_ks = """
        nvdimm use --namespace=namespace0.0
        """
        expected_ks = """
        # NVDIMM devices setup
        nvdimm use --namespace=namespace0.0
        nvdimm use --namespace=namespace1.0
        """
        self._read(input_ks)
        self._check_ignored(["pmem1", "pmem2"])
        self._use(["namespace0.0", "namespace1.0"])
        self._check(expected_ks)

    def ksuse_use_none_test(self):
        """Test updating of nvdimm commands based on device selection in UI."""
        input_ks = """
        nvdimm use --namespace=namespace0.0
        """
        expected_ks = """
        """
        self._read(input_ks)
        self._check_ignored(["pmem1", "pmem2"])
        self._use([])
        self._check(expected_ks)

    def ksnone_use2_test(self):
        """Test updating of nvdimm commands based on device selection in UI."""
        input_ks = """
        """
        expected_ks = """
        # NVDIMM devices setup
        nvdimm use --namespace=namespace0.0
        nvdimm use --namespace=namespace1.0
        """
        self._read(input_ks)
        self._check_ignored(["pmem0", "pmem1", "pmem2"])
        self._use(["namespace0.0", "namespace1.0"])
        self._check(expected_ks)

    def ksnone_repeated_use_test(self):
        """Test updating of nvdimm commands based on device selection in UI."""
        input_ks = """
        """
        expected_ks = """
        # NVDIMM devices setup
        nvdimm use --namespace=namespace0.0
        """
        self._read(input_ks)
        self._check_ignored(["pmem0", "pmem1", "pmem2"])
        self._use(["namespace0.0"])
        self._use(["namespace0.0"])
        self._check(expected_ks)

    def ksnone_use_none_test(self):
        """Test updating of nvdimm commands based on device selection in UI."""
        input_ks = """
        """
        expected_ks = """
        """
        self._read(input_ks)
        self._check_ignored(["pmem0", "pmem1", "pmem2"])
        self._use([])
        self._check(expected_ks)

    def ksnone_repeated_use_2_test(self):
        """Test updating of nvdimm commands based on device selection in UI."""
        input_ks = """
        """
        expected_ks = """
        # NVDIMM devices setup
        nvdimm use --namespace=namespace1.0
        """
        self._read(input_ks)
        self._check_ignored(["pmem0", "pmem1", "pmem2"])
        self._use(["namespace0.0"])
        # Next use should override the previous
        self._use(["namespace1.0"])
        self._check(expected_ks)

    def ksuse_another_use_test(self):
        """Test updating of nvdimm commands based on device selection in UI."""
        input_ks = """
        nvdimm use --namespace=namespace1.0
        """
        expected_ks = """
        # NVDIMM devices setup
        nvdimm use --namespace=namespace0.0
        """
        self._read(input_ks)
        self._check_ignored(["pmem0", "pmem2"])
        self._use(["namespace0.0"])
        self._check(expected_ks)

    def ksuse_none_test(self):
        """Test updating of nvdimm commands based on device selection in UI."""
        input_ks = """
        nvdimm use --namespace=namespace1.0
        """
        expected_ks = """
        """
        self._read(input_ks)
        self._check_ignored(["pmem0", "pmem2"])
        self._use([])
        self._check(expected_ks)

    def ksreconfigure_use_test(self):
        """Test updating of nvdimm commands based on device selection in UI."""
        input_ks = """
        nvdimm reconfigure --namespace=namespace0.0 --mode=sector --sectorsize=512
        """
        expected_ks = """
        # NVDIMM devices setup
        nvdimm reconfigure --namespace=namespace0.0 --mode=sector --sectorsize=512
        """
        self._read(input_ks)
        self._check_ignored(["pmem1", "pmem2"])
        self._use(["namespace0.0"])
        self._check(expected_ks)

    def ksreconfigure_use_none_test(self):
        """Test updating of nvdimm commands based on device selection in UI."""
        input_ks = """
        nvdimm reconfigure --namespace=namespace0.0 --mode=sector --sectorsize=512
        """
        expected_ks = """
        # NVDIMM devices setup
        nvdimm reconfigure --namespace=namespace0.0 --mode=sector --sectorsize=512
        """
        self._read(input_ks)
        self._check_ignored(["pmem1", "pmem2"])
        # Even when not used, the reconfiguration should go to generated kicksart
        self._use([])
        self._check(expected_ks)

    def ksreconfigure_another_use_test(self):
        """Test updating of nvdimm commands based on device selection in UI."""
        input_ks = """
        nvdimm reconfigure --namespace=namespace0.0 --mode=sector --sectorsize=512
        """
        expected_ks = """
        # NVDIMM devices setup
        nvdimm reconfigure --namespace=namespace0.0 --mode=sector --sectorsize=512
        nvdimm use --namespace=namespace1.0
        """
        self._read(input_ks)
        self._check_ignored(["pmem1", "pmem2"])
        self._use(["namespace1.0"])
        self._check(expected_ks)

    def ksreconfigure_ksuse_another_use_test(self):
        """Test updating of nvdimm commands based on device selection in UI."""
        input_ks = """
        nvdimm reconfigure --namespace=namespace0.0 --mode=sector --sectorsize=512
        nvdimm use --namespace=namespace1.0
        """
        expected_ks = """
        # NVDIMM devices setup
        nvdimm reconfigure --namespace=namespace0.0 --mode=sector --sectorsize=512
        """
        self._read(input_ks)
        self._check_ignored(["pmem2"])
        self._use(["namespace0.0"])
        self._check(expected_ks)

    def ksreconfigure_2_use_1_test(self):
        """Test updating of nvdimm commands based on device selection in UI."""
        input_ks = """
        nvdimm reconfigure --namespace=namespace0.0 --mode=sector --sectorsize=512
        nvdimm reconfigure --namespace=namespace1.0 --mode=sector --sectorsize=512
        """
        expected_ks = """
        # NVDIMM devices setup
        nvdimm reconfigure --namespace=namespace0.0 --mode=sector --sectorsize=512
        nvdimm reconfigure --namespace=namespace1.0 --mode=sector --sectorsize=512
        """
        self._read(input_ks)
        self._check_ignored(["pmem2"])
        self._use(["namespace0.0"])
        self._check(expected_ks)

    # Test reconfigure and use in UI
    # (if _reconfigure is done in UI, _use is always done as well)

    def ksnone_reconfigure_use_test(self):
        """Test updating of nvdimm commands based on device reconfiguration in UI."""
        input_ks = """
        """
        expected_ks = """
        # NVDIMM devices setup
        nvdimm reconfigure --namespace=namespace0.0 --mode=sector --sectorsize=512
        """
        self._read(input_ks)
        self._check_ignored(["pmem0", "pmem1", "pmem2"])
        self._reconfigure("namespace0.0", 512)
        self._use(["namespace0.0"])
        self._check(expected_ks)

    def ksnone_repeated_reconfigure_use_test(self):
        """Test updating of nvdimm commands based on device reconfiguration in UI."""
        input_ks = """
        """
        expected_ks = """
        # NVDIMM devices setup
        nvdimm reconfigure --namespace=namespace0.0 --mode=sector --sectorsize=4096
        """
        self._read(input_ks)
        self._check_ignored(["pmem0", "pmem1", "pmem2"])
        self._reconfigure("namespace0.0", 512)
        self._reconfigure("namespace0.0", 4096)
        self._use(["namespace0.0"])
        self._check(expected_ks)

    def ksnone_repeated_reconfigure_repeated_use_test(self):
        """Test updating of nvdimm commands based on device reconfiguration in UI."""
        input_ks = """
        """
        expected_ks = """
        # NVDIMM devices setup
        nvdimm reconfigure --namespace=namespace0.0 --mode=sector --sectorsize=512
        nvdimm reconfigure --namespace=namespace1.0 --mode=sector --sectorsize=512
        """
        self._read(input_ks)
        self._check_ignored(["pmem0", "pmem1", "pmem2"])
        self._reconfigure("namespace0.0", 512)
        self._use(["namespace0.0"])
        self._reconfigure("namespace1.0", 512)
        # Even when not used, reconfiguration goes to generated ks
        self._use(["namespace1.0"])
        self._check(expected_ks)

    def ksuse_reconfigure_other_use_other_test(self):
        """Test updating of nvdimm commands based on device reconfiguration in UI."""
        input_ks = """
        nvdimm use --namespace=namespace0.0
        """
        expected_ks = """
        # NVDIMM devices setup
        nvdimm reconfigure --namespace=namespace1.0 --mode=sector --sectorsize=512
        """
        self._read(input_ks)
        self._check_ignored(["pmem1", "pmem2"])
        self._reconfigure("namespace1.0", 512)
        self._use(["namespace1.0"])
        self._check(expected_ks)

    def ksuse_2_reconfigure_1_use_2_test(self):
        """Test updating of nvdimm commands based on device reconfiguration in UI."""
        input_ks = """
        nvdimm use --namespace=namespace0.0
        nvdimm use --namespace=namespace1.0
        """
        expected_ks = """
        # NVDIMM devices setup
        nvdimm reconfigure --namespace=namespace1.0 --mode=sector --sectorsize=512
        nvdimm use --namespace=namespace0.0
        """
        self._read(input_ks)
        self._check_ignored(["pmem2"])
        self._reconfigure("namespace1.0", 512)
        self._use(["namespace0.0", "namespace1.0"])
        self._check(expected_ks)

    def ksuse_reconfigure_other_use_none_test(self):
        """Test updating of nvdimm commands based on device reconfiguration in UI."""
        input_ks = """
        nvdimm use --namespace=namespace0.0
        """
        expected_ks = """
        # NVDIMM devices setup
        nvdimm reconfigure --namespace=namespace1.0 --mode=sector --sectorsize=512
        """
        self._read(input_ks)
        self._check_ignored(["pmem1", "pmem2"])
        self._reconfigure("namespace1.0", 512)

        # Even when not used, the reconfiguration should go to generated kickstart.
        self._use([])
        self._check(expected_ks)

    @patch("pyanaconda.modules.storage.kickstart.device_matches")
    def ksuse_blockdevs_test(self, device_matches):
        """Test using blockdevs."""
        input_ks = """
        nvdimm use --blockdev=pmem0,pmem2
        """
        expected_ks = """
        # NVDIMM devices setup
        nvdimm use --namespace=namespace0.0
        """
        device_matches.return_value = ["pmem0", "pmem2"]
        self._read(input_ks)
        self._check_ignored(["pmem1", "pmem2"])
        self._use(["namespace0.0"])
        self._check(expected_ks)
