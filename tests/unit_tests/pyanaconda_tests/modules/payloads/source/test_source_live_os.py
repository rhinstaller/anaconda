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
# Red Hat Author(s): Jiri Konecny <jkonecny@redhat.com>
#
import unittest
from unittest.mock import patch

import pytest

from pyanaconda.core.constants import SOURCE_TYPE_LIVE_OS_IMAGE
from pyanaconda.modules.common.constants.interfaces import PAYLOAD_SOURCE_LIVE_OS
from pyanaconda.modules.common.errors.payload import SourceSetupError
from pyanaconda.modules.payloads.constants import SourceState
from pyanaconda.modules.payloads.source.live_os.initialization import (
    DetectLiveOSImageTask,
    SetupLiveOSResult,
    SetUpLiveOSSourceTask,
)
from pyanaconda.modules.payloads.source.live_os.live_os import LiveOSSourceModule
from pyanaconda.modules.payloads.source.live_os.live_os_interface import (
    LiveOSSourceInterface,
)
from tests.unit_tests.pyanaconda_tests import (
    check_dbus_property,
    check_task_creation,
    patch_dbus_publish_object,
)


class LiveOSSourceInterfaceTestCase(unittest.TestCase):
    """Test the DBus interface of the Live OS source."""

    def setUp(self):
        self.module = LiveOSSourceModule()
        self.interface = LiveOSSourceInterface(self.module)

    def test_type(self):
        """Test the source type."""
        assert self.interface.Type == SOURCE_TYPE_LIVE_OS_IMAGE

    def test_description(self):
        """Test the source description."""
        assert self.interface.Description == "Live OS"

    def test_defaults(self):
        """Test the default values."""
        assert self.interface.ImagePath == ""

    def test_image_path(self):
        """Test the ImagePath property."""
        check_dbus_property(
            PAYLOAD_SOURCE_LIVE_OS,
            self.interface,
            "ImagePath",
            "/my/fake/path"
        )

    @patch_dbus_publish_object
    def test_detect_image_with_task(self, publisher):
        """Test the DetectImageWithTask method."""
        task_path = self.interface.DetectImageWithTask()
        check_task_creation(task_path, publisher, DetectLiveOSImageTask)


class LiveOSSourceTestCase(unittest.TestCase):
    """Test the Live OS source."""

    def setUp(self):
        self.module = LiveOSSourceModule()

    def test_network_required(self):
        """Test the network_required property."""
        assert self.module.network_required is False

    @patch.object(SetUpLiveOSSourceTask, "run")
    def test_required_space(self, runner):
        """Test the required_space property."""
        assert self.module.required_space == 0

        runner.return_value = SetupLiveOSResult(12345)

        tasks = self.module.set_up_with_tasks()
        for task in tasks:
            task.run_with_signals()

        runner.assert_called_once_with()
        assert self.module.required_space == 12345

    def test_get_state(self):
        """Test the source state."""
        # LiveOS source doesn't have a traditional mount state since it reuses existing mounts
        assert self.module.get_state() == SourceState.NOT_APPLICABLE

    def test_set_up_with_tasks(self):
        """Test the set up tasks."""
        tasks = self.module.set_up_with_tasks()
        assert len(tasks) == 1
        assert isinstance(tasks[0], SetUpLiveOSSourceTask)

    def test_tear_down_with_tasks(self):
        """Test the tear down tasks."""
        tasks = self.module.tear_down_with_tasks()
        assert len(tasks) == 0  # No tear-down tasks needed for LiveOS

    def test_repr(self):
        """Test the string representation."""
        self.module.set_image_path("/some/path")
        assert repr(self.module) == "Source(type='LIVE_OS_IMAGE', image='/some/path')"


class LiveOSSourceTasksTestCase(unittest.TestCase):
    """Test the tasks of the Live OS source."""
    @patch("pyanaconda.modules.payloads.source.live_os.initialization.execWithCapture")
    def test_live_os_image_size(self, exec_mock):
        """Test Live OS image size calculation."""
        exec_mock.return_value = "29696      /path/to/base/image/"

        task = SetUpLiveOSSourceTask(
                "/path/to/mount/source/image"
        )

        assert task._calculate_required_space() == 29696

    @patch("pyanaconda.modules.payloads.source.live_os.initialization.execWithCapture")
    @patch("pyanaconda.modules.payloads.source.live_os.initialization.os.path.exists")
    @patch("pyanaconda.modules.payloads.source.live_os.initialization.stat")
    @patch("pyanaconda.modules.payloads.source.live_os.initialization.os.stat")
    def test_detect_live_os_image_failed(self, os_stat_mock, stat_mock, exists_mock, exec_mock):
        """Test Live OS image detection failed missing file."""
        stat_mock.S_ISBLK.side_effect = FileNotFoundError()
        exists_mock.side_effect = [False]

        with pytest.raises(SourceSetupError) as cm:
            task = DetectLiveOSImageTask()
            task.run()

        assert str(cm.value) == "No Live OS image found!"

        exists_mock.side_effect = [True]
        exec_mock.side_effect = FileNotFoundError()

        with pytest.raises(SourceSetupError) as cm:
            task = DetectLiveOSImageTask()
            task.run()

        assert str(cm.value) == "No Live OS image found!"

        exists_mock.side_effect = [True]
        exec_mock.return_value = ""

        with pytest.raises(SourceSetupError) as cm:
            task = DetectLiveOSImageTask()
            task.run()

        assert str(cm.value) == "No Live OS image found!"

    @patch("pyanaconda.modules.payloads.source.live_os.initialization.execWithCapture")
    @patch("pyanaconda.modules.payloads.source.live_os.initialization.os.path.exists")
    @patch("pyanaconda.modules.payloads.source.live_os.initialization.stat")
    @patch("pyanaconda.modules.payloads.source.live_os.initialization.os.stat")
    def test_detect_live_os_image(self, os_stat_mock, stat_mock, exists_mock, exec_mock):
        """Test Live OS image detection."""
        stat_mock.S_ISBLK.side_effect = [True, True]

        task = DetectLiveOSImageTask()
        detected_image = task.run()
        assert detected_image == "/dev/mapper/live-base"

        stat_mock.S_ISBLK.side_effect = [False, True]

        task = DetectLiveOSImageTask()
        detected_image = task.run()
        assert detected_image == "/dev/mapper/live-osimg-min"

        stat_mock.S_ISBLK.side_effect = [False, False]
        exists_mock.return_value = True
        exec_mock.return_value = "/my/device"

        task = DetectLiveOSImageTask()
        detected_image = task.run()
        assert detected_image == "/my/device"

    @patch.object(SetUpLiveOSSourceTask, "_calculate_required_space", return_value=12345)
    def test_setup_install_source_task_name(self, required_space):
        """Test Live OS Source setup installation source task name."""
        task = SetUpLiveOSSourceTask(
                "/path/to/mount/source/image"
            )

        assert task.name == "Set up a Live OS image"

    @patch.object(SetUpLiveOSSourceTask, "_calculate_required_space", return_value=12345)
    def test_setup_install_source_task_run(self, calculate_space):
        """Test Live OS Source setup installation source task run."""
        result = SetUpLiveOSSourceTask(
            "/path/to/mount/source/image"
        ).run()

        assert isinstance(result, SetupLiveOSResult)
        assert result.required_space == 12345
        calculate_space.assert_called_once_with()

    @patch("pyanaconda.modules.payloads.source.live_os.initialization.execWithCapture")
    def test_setup_install_source_task_missing_mount(self, exec_mock):
        """Test Live OS Source setup installation source task with missing mount point."""
        exec_mock.side_effect = FileNotFoundError("du: cannot access '/nonexistent': No such file or directory")

        with pytest.raises(SourceSetupError) as cm:
            SetUpLiveOSSourceTask(
                "/nonexistent"
            ).run()

        assert "du: cannot access" in str(cm.value) or "No such file" in str(cm.value)

    @patch("pyanaconda.modules.payloads.source.live_os.initialization.execWithCapture")
    def test_setup_install_source_task_calculate_space_error(self, exec_mock):
        """Test Live OS Source setup installation source task with space calculation error."""
        exec_mock.side_effect = OSError("Permission denied")

        with pytest.raises(SourceSetupError) as cm:
            SetUpLiveOSSourceTask(
                "/path/to/mount/source/image"
            ).run()

        assert "Permission denied" in str(cm.value)

    @patch("pyanaconda.modules.payloads.source.live_os.initialization.execWithCapture")
    def test_setup_install_source_task_du_command_error(self, exec_mock):
        """Test Live OS Source setup installation source task with du command error."""
        exec_mock.side_effect = OSError("du: cannot execute")

        with pytest.raises(SourceSetupError) as cm:
            SetUpLiveOSSourceTask(
                "/path/to/mount/source/image"
            ).run()

        assert "du: cannot execute" in str(cm.value)
