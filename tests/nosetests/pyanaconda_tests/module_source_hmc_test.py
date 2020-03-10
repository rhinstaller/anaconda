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

from unittest.mock import patch, call

from pyanaconda.core.constants import INSTALL_TREE
from pyanaconda.modules.common.errors.payload import SourceSetupError
from pyanaconda.modules.payloads.constants import SourceType
from pyanaconda.modules.payloads.source.hmc.hmc import HMCSourceModule
from pyanaconda.modules.payloads.source.hmc.hmc_interface import HMCSourceInterface
from pyanaconda.modules.payloads.source.hmc.initialization import TearDownHMCSourceTask, \
    SetUpHMCSourceTask


class HMCSourceInterfaceTestCase(unittest.TestCase):
    """Test the DBus interface of the SE/HMC source module."""

    def setUp(self):
        self.module = HMCSourceModule()
        self.interface = HMCSourceInterface(self.module)

    def type_test(self):
        """Test the type of SE/HMC."""
        self.assertEqual(SourceType.HMC.value, self.interface.Type)


class HMCSourceModuleTestCase(unittest.TestCase):
    """Test the SE/HMC source module."""

    def setUp(self):
        self.module = HMCSourceModule()

    @patch("os.path.ismount")
    def ready_state_test(self, ismount):
        """Check whether SE/HMC is ready."""
        ismount.return_value = False
        self.assertFalse(self.module.is_ready())

        ismount.reset_mock()
        ismount.return_value = True

        self.assertTrue(self.module.is_ready())
        ismount.assert_called_once_with(INSTALL_TREE)

    def set_up_with_tasks_test(self):
        """Get tasks to set up SE/HMC."""
        tasks = self.module.set_up_with_tasks()
        self.assertEqual(len(tasks), 1)

        task = tasks[0]
        self.assertIsInstance(task, SetUpHMCSourceTask)
        self.assertEqual(task._target_mount, INSTALL_TREE)

    def tear_down_with_tasks_test(self):
        """Get tasks to tear down SE/HMC."""
        tasks = self.module.tear_down_with_tasks()
        self.assertEqual(len(tasks), 1)

        task = tasks[0]
        self.assertIsInstance(task, TearDownHMCSourceTask)


class HMCSourceTasksTestCase(unittest.TestCase):
    """Test tasks of the SE/HMC source module."""

    @patch("pyanaconda.modules.payloads.source.hmc.initialization.execWithRedirect")
    def set_up_with_tasks_test(self, execute):
        """Set up SE/HMC."""
        with tempfile.TemporaryDirectory() as d:
            task = SetUpHMCSourceTask(d)

            execute.side_effect = [1, 1]
            with self.assertRaises(SourceSetupError):
                task.run()

            execute.side_effect = [0, 1]
            with self.assertRaises(SourceSetupError):
                task.run()

            execute.reset_mock()
            execute.side_effect = [0, 0]
            task.run()

            execute.assert_has_calls([
                call("/usr/sbin/lshmc", []),
                call("/usr/bin/hmcdrvfs", [d])
            ])

    @patch("pyanaconda.modules.payloads.source.hmc.initialization.unmount")
    def tear_down_with_tasks_test(self, unmount):
        """Tear down SE/HMC."""
        with tempfile.TemporaryDirectory() as d:
            task = TearDownHMCSourceTask(d)
            task.run()
            unmount.assert_called_once_with(d)
