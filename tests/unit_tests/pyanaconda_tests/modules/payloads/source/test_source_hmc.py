#
# Copyright (C) 2020  Red Hat, Inc.
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
#
import tempfile
import unittest
from unittest.mock import call, patch

import pytest

from pyanaconda.core.constants import SOURCE_TYPE_HMC
from pyanaconda.modules.common.errors.payload import SourceSetupError
from pyanaconda.modules.payloads.constants import SourceState
from pyanaconda.modules.payloads.source.hmc.hmc import HMCSourceModule
from pyanaconda.modules.payloads.source.hmc.hmc_interface import HMCSourceInterface
from pyanaconda.modules.payloads.source.hmc.initialization import SetUpHMCSourceTask
from pyanaconda.modules.payloads.source.mount_tasks import TearDownMountTask


class HMCSourceInterfaceTestCase(unittest.TestCase):
    """Test the DBus interface of the SE/HMC source module."""

    def setUp(self):
        self.module = HMCSourceModule()
        self.interface = HMCSourceInterface(self.module)

    def test_type(self):
        """Test the type of SE/HMC."""
        assert SOURCE_TYPE_HMC == self.interface.Type

    def test_description(self):
        """Test the description of SE/HMC."""
        assert "Local media via SE/HMC" == self.interface.Description


class HMCSourceModuleTestCase(unittest.TestCase):
    """Test the SE/HMC source module."""

    def setUp(self):
        self.module = HMCSourceModule()

    def test_network_required(self):
        """Test the property network_required."""
        assert self.module.network_required is False

    def test_required_space(self):
        """Test the required_space property."""
        assert self.module.required_space == 0

    @patch("os.path.ismount")
    def test_get_state(self, ismount_mock):
        """Test SE/HMC source state."""
        ismount_mock.return_value = False
        assert SourceState.UNREADY == self.module.get_state()

        ismount_mock.reset_mock()
        ismount_mock.return_value = True

        assert SourceState.READY == self.module.get_state()

        ismount_mock.assert_called_once_with(self.module.mount_point)

    def test_set_up_with_tasks(self):
        """Get tasks to set up SE/HMC."""
        tasks = self.module.set_up_with_tasks()
        assert len(tasks) == 1

        task = tasks[0]
        assert isinstance(task, SetUpHMCSourceTask)
        assert task._target_mount == self.module.mount_point

    def test_tear_down_with_tasks(self):
        """Get tasks to tear down SE/HMC."""
        tasks = self.module.tear_down_with_tasks()
        assert len(tasks) == 1

        task = tasks[0]
        assert isinstance(task, TearDownMountTask)

    def test_repr(self):
        assert repr(self.module) == "Source(type='HMC')"


class HMCSourceTasksTestCase(unittest.TestCase):
    """Test tasks of the SE/HMC source module."""

    @patch("pyanaconda.modules.payloads.source.hmc.initialization.execWithRedirect")
    def test_set_up_with_tasks(self, execute):
        """Set up SE/HMC."""
        with tempfile.TemporaryDirectory() as d:
            task = SetUpHMCSourceTask(d)

            execute.side_effect = [1, 1]
            with pytest.raises(SourceSetupError):
                task.run()

            execute.side_effect = [0, 1]
            with pytest.raises(SourceSetupError):
                task.run()

            execute.reset_mock()
            execute.side_effect = [0, 0]
            task.run()

            execute.assert_has_calls([
                call("/usr/sbin/lshmc", []),
                call("/usr/bin/hmcdrvfs", [d])
            ])
