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
import unittest
from unittest.mock import patch

from pyanaconda.core.constants import INSTALL_TREE
from pyanaconda.modules.common.errors.payload import SourceSetupError
from pyanaconda.modules.payloads.constants import SourceType, SourceState
from pyanaconda.modules.payloads.source.mount_tasks import SetUpMountTask, TearDownMountTask
from pyanaconda.modules.payloads.source.source_base import MountingSourceBase

mount_location = "/some/dir"


class DummyMountingSourceSubclass(MountingSourceBase):
    """Dummy class to test code in its abstract ancestor."""

    @property
    def type(self):
        return SourceType.URL

    @property
    def description(self):
        return "description"

    def for_publication(self):
        return None

    def set_up_with_tasks(self):
        return []


class DummySetUpMountTaskSubclass(SetUpMountTask):
    """Dummy class to test code in its abstract ancestor."""

    @property
    def name(self):
        return "Set up Dummy Installation Source"

    def _do_mount(self):
        pass


class SourceBaseTestCase(unittest.TestCase):

    def source_repr_test(self):
        module = DummyMountingSourceSubclass()
        self.assertEqual(repr(module), "Source(URL)")


class MountingSourceBaseTestCase(unittest.TestCase):

    def counter_test(self):
        """Mount path in mount source base gets incremental numbers."""
        module = DummyMountingSourceSubclass()
        self.assertTrue(module.mount_point.startswith(INSTALL_TREE + "/mount-"))
        first_counter = int(module.mount_point.split("-")[1])

        module = DummyMountingSourceSubclass()
        second_counter = int(module.mount_point.split("-")[1])

        self.assertEqual(first_counter, second_counter - 1)

    @patch("os.path.ismount")
    def ready_state_test(self, ismount_mock):
        """Mount source base ready state for set up."""
        ismount_mock.return_value = False
        module = DummyMountingSourceSubclass()
        self.assertEqual(SourceState.UNREADY, module.get_state())

        ismount_mock.reset_mock()
        ismount_mock.return_value = True

        self.assertEqual(SourceState.READY, module.get_state())

        ismount_mock.assert_called_once_with(module.mount_point)

    def tear_down_test(self):
        """Mount source base tear down."""
        module = DummyMountingSourceSubclass()
        tasks = module.tear_down_with_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(type(tasks[0]), TearDownMountTask)


class TearDownMountTaskTestCase(unittest.TestCase):

    def name_test(self):
        """Tear down mount source task name."""
        task = TearDownMountTask(mount_location)
        self.assertEqual(task.name, "Tear down mount installation source")

    @patch("pyanaconda.modules.payloads.source.mount_tasks.unmount", return_value=True)
    def run_success_test(self, unmount_mock):
        """Tear down mount source task execution."""
        task = TearDownMountTask(mount_location)
        task.run()
        unmount_mock.assert_called_once_with(mount_location)


class SetUpMountTaskTestCase(unittest.TestCase):

    @patch("pyanaconda.modules.payloads.source.mount_tasks.os.path.ismount", return_value=False)
    def run_success_test(self, ismount_mock):
        """Set up mount base task success case."""
        task = DummySetUpMountTaskSubclass(mount_location)
        task.run()
        ismount_mock.assert_called_once_with(mount_location)

    @patch("pyanaconda.modules.payloads.source.mount_tasks.os.path.ismount", return_value=True)
    def run_failure_test(self, ismount_mock):
        """Set up mount base task when already mounted."""
        task = DummySetUpMountTaskSubclass(mount_location)
        with self.assertRaises(SourceSetupError) as cm:
            task.run()

        self.assertEqual(str(cm.exception), "The mount point /some/dir is already in use.")
        ismount_mock.assert_called_once_with(mount_location)
