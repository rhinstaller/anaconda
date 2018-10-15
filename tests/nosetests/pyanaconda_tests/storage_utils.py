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
import unittest
from textwrap import dedent

from pyanaconda.storage_utils import nvdimm_update_ksdata_for_used_devices, \
    nvdimm_update_ksdata_after_reconfiguration
from pyanaconda.core.kickstart import VERSION, KickstartSpecification, commands as COMMANDS
from pyanaconda.core.kickstart.specification import KickstartSpecificationHandler, KickstartSpecificationParser

from pykickstart.constants import NVDIMM_MODE_SECTOR


class NvdimmKickstartSpecification(KickstartSpecification):
    """Kickstart specification of nvdimm command."""

    version = VERSION

    commands = {
        "nvdimm": COMMANDS.Nvdimm
    }

    commands_data = {
        "NvdimmData": COMMANDS.NvdimmData
    }


class UpdateNvdimmDataTestCase(unittest.TestCase):
    """Test updating of nvdimm command from UI.

    The update is done:
    - always by disk selection in UI.
    - optionally by reconfiguring NVDIMM in UI.
    """

    def setUp(self):
        nvdimm_ks_spec = NvdimmKickstartSpecification()
        self.handler = KickstartSpecificationHandler(nvdimm_ks_spec)
        self.parser = KickstartSpecificationParser(self.handler, nvdimm_ks_spec)

    def _read(self, input_ks):
        self.parser.readKickstartFromString(input_ks)

    def _use(self, namespaces):
        """Represents update for NVDIMM disks selected in UI."""
        nvdimm_update_ksdata_for_used_devices(self.handler,
                                              namespaces=namespaces)

    def _reconfigure(self, namespace, sectorsize):
        """Represents update for NVDIMM disk reconfigured in UI."""
        nvdimm_update_ksdata_after_reconfiguration(self.handler,
                                                   namespace=namespace,
                                                   mode=NVDIMM_MODE_SECTOR,
                                                   sectorsize=sectorsize)

    def _check(self, expected_ks):
        self.assertEqual(str(self.handler.nvdimm).strip(), dedent(expected_ks).strip())

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
        self._reconfigure("namespace1.0", 512)
        # Even when not used, the reconfiguration should go to generated kicksart
        self._use([])
        print(self.handler.nvdimm)
        self._check(expected_ks)
