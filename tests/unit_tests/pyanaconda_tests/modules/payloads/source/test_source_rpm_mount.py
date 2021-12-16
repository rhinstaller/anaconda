#
# Copyright (C) 2021  Red Hat, Inc.
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

from unittest.mock import patch, Mock

from pyanaconda.core.constants import SOURCE_TYPE_RPM_MOUNT
from pyanaconda.modules.common.constants.interfaces import PAYLOAD_SOURCE_RPM_MOUNT
from pyanaconda.modules.payloads.constants import SourceType, SourceState
from pyanaconda.modules.payloads.source.rpm_mount.rpm_mount import RPMMountSourceModule
from pyanaconda.modules.payloads.source.rpm_mount.rpm_mount_interface import \
    RPMMountSourceInterface
from pyanaconda.modules.payloads.source.rpm_mount.initialization import SetUpRPMMountSourceTask

from tests.unit_tests.pyanaconda_tests import check_dbus_property, PropertiesChangedCallback


TEST_PATH = "/my/cool/path"


class RPMMountSourceInterfaceTestCase(unittest.TestCase):

    def setUp(self):
        self.module = RPMMountSourceModule()
        self.interface = RPMMountSourceInterface(self.module)

        self.callback = PropertiesChangedCallback()
        self.interface.PropertiesChanged.connect(self.callback)

    def test_type(self):
        """Test RPM Mount source has a correct type specified."""
        assert SOURCE_TYPE_RPM_MOUNT == self.interface.Type

    def test_description(self):
        """Test RPM Mount source description."""
        self.interface.SetPath("/run/run/run")
        assert self.interface.Description == "RPM Mount /run/run/run"

    def test_path_empty_properties(self):
        """Test RPM Mount source path property when not set."""
        assert self.interface.Path == ""

    def test_url_properties(self):
        """Test RPM source path property is correctly set."""
        check_dbus_property(
            PAYLOAD_SOURCE_RPM_MOUNT,
            self.interface,
            "Path",
            "/run/install/repo-or-not"
        )


class RPMMountSourceTestCase(unittest.TestCase):

    def setUp(self):
        self.module = RPMMountSourceModule()

    def test_type(self):
        """Test RPM mount source module has a correct type."""
        assert SourceType.RPM_MOUNT == self.module.type

    def test_network_required(self):
        """Test the property network_required."""
        assert self.module.network_required is False

    def test_required_space(self):
        """Test the required_space property."""
        assert self.module.required_space == 0

    def test_state(self):
        """Test RPM mount source state."""
        assert SourceState.UNREADY == self.module.get_state()

        task = self.module.set_up_with_tasks()[0]
        task.get_result = Mock(return_value=True)
        task.succeeded_signal.emit()
        assert SourceState.READY == self.module.get_state()

    def test_set_up_with_tasks(self):
        """Test RPM Mount Source set up call."""
        task_classes = [
            SetUpRPMMountSourceTask
        ]

        # task will not be public so it won't be published
        tasks = self.module.set_up_with_tasks()

        # Check the number of the tasks
        task_number = len(task_classes)
        assert task_number == len(tasks)

        for i in range(task_number):
            assert isinstance(tasks[i], task_classes[i])

    def test_tear_down_with_tasks(self):
        """Test RPM Mount Source tear down tasks."""
        # task will not be public so it won't be published
        tasks = self.module.tear_down_with_tasks()

        assert len(tasks) == 0

    def test_path_property(self):
        """Test RPM mount source path property is correctly set."""
        self.module.set_path("/my/fun/path")
        assert self.module.path == "/my/fun/path"

    def test_repr(self):
        """Test RPM mount source repr call."""
        self.module.set_path("/my/path")
        assert repr(self.module) == "Source(type='RPM_MOUNT', path='/my/path')"


class RPMMountSourceSetupTaskTestCase(unittest.TestCase):

    def test_setup_install_source_task_name(self):
        """Test RPM Mount source setup installation source task name."""
        task = SetUpRPMMountSourceTask(TEST_PATH)
        assert task.name == "Set up RPM Mount Installation Source"

    @patch("pyanaconda.modules.payloads.source.rpm_mount.initialization.verify_valid_repository")
    def test_verify_repository_success(self, verify_valid_repository_mock):
        """Test RPM mount source setup have valid repository."""
        verify_valid_repository_mock.return_value = True

        task = SetUpRPMMountSourceTask(TEST_PATH)
        result = task.run()

        verify_valid_repository_mock.assert_called_once_with(TEST_PATH)

        assert result is True

    @patch("pyanaconda.modules.payloads.source.rpm_mount.initialization.verify_valid_repository")
    def test_verify_repository_failure(self, verify_valid_repository_mock):
        """Test RPM mount source setup have invalid repository."""
        verify_valid_repository_mock.return_value = False

        task = SetUpRPMMountSourceTask(TEST_PATH)
        result = task.run()

        verify_valid_repository_mock.assert_called_once_with(TEST_PATH)

        assert result is False
