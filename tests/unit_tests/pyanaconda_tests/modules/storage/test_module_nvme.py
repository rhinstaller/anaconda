#
# Copyright (C) 2023  Red Hat, Inc.
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
# Red Hat Author(s): Vojtech Trefny <vtrefny@redhat.com>
#
import unittest

from unittest.mock import patch

from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.modules.storage.nvme import NVMEModule
from pyanaconda.modules.storage.nvme.nvme_interface import NVMEInterface


class NVMEInterfaceTestCase(unittest.TestCase):
    """Test DBus interface of the NVMe module."""

    def setUp(self):
        """Set up the module."""
        self.nvme_module = NVMEModule()
        self.nvme_interface = NVMEInterface(self.nvme_module)

    @patch('pyanaconda.modules.storage.nvme.nvme.nvme')
    def test_write_configuration(self, nvme):
        """Test WriteConfiguration."""
        self.nvme_interface.WriteConfiguration()
        nvme.write.assert_called_once_with(conf.target.system_root)
