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
import os
from tempfile import TemporaryDirectory
from textwrap import dedent
from unittest import TestCase
from unittest.mock import DEFAULT, Mock, create_autospec, patch

import pytest

from pyanaconda.core.constants import SOURCE_TYPE_LIVE_OS_IMAGE
from pyanaconda.modules.common.containers import PayloadContainer, TaskContainer
from pyanaconda.modules.common.errors.general import UnavailableValueError
from pyanaconda.modules.common.errors.payload import (
    SourceSetupError,
    SourceTearDownError,
)
from pyanaconda.modules.common.task import Task
from pyanaconda.modules.payloads.base.initialization import (
    SetUpSourcesTask,
    TearDownSourcesTask,
)
from pyanaconda.modules.payloads.constants import PayloadType, SourceType
from pyanaconda.modules.payloads.installation import (
    CopyDriverDisksFilesTask,
    PrepareSystemForInstallationTask,
)
from pyanaconda.modules.payloads.payload.dnf.dnf import DNFModule
from pyanaconda.modules.payloads.payload.live_image.live_image import LiveImageModule
from pyanaconda.modules.payloads.payload.live_os.live_os import LiveOSModule
from pyanaconda.modules.payloads.payloads import PayloadsService
from pyanaconda.modules.payloads.payloads_interface import PayloadsInterface
from pyanaconda.modules.payloads.source.live_os.live_os import LiveOSSourceModule
from pyanaconda.modules.payloads.source.source_base import PayloadSourceBase
from tests.unit_tests.pyanaconda_tests import (
    check_dbus_object_creation,
    patch_dbus_publish_object,
)
from tests.unit_tests.pyanaconda_tests.modules.payloads.payload.module_payload_shared import (
    PayloadKickstartSharedTest,
)


class PayloadsInterfaceTestCase(TestCase):

    def setUp(self):
        """Set up the payload module."""
        self.payload_module = PayloadsService()
        self.payload_interface = PayloadsInterface(self.payload_module)

        self.shared_ks_tests = PayloadKickstartSharedTest(self.payload_module,
                                                          self.payload_interface)

    def test_kickstart_properties(self):
        """Test kickstart properties."""
        assert self.payload_interface.KickstartCommands == [
            "cdrom",
            "harddrive",
            "hmc",
            "liveimg",
            "module",
            "nfs",
            "ostreecontainer",
            "ostreesetup",
            "bootc",
            "repo",
            "url"
        ]
        assert self.payload_interface.KickstartSections == [
            "packages"
        ]
        assert self.payload_interface.KickstartAddons == []

    def test_no_kickstart(self):
        """Test kickstart is not set to the payloads service."""
        ks_in = None
        ks_out = ""
        self.shared_ks_tests.check_kickstart(ks_in, ks_out, expected_publish_calls=0)

    def test_kickstart_empty(self):
        """Test kickstart is empty for the payloads service."""
        ks_in = ""
        ks_out = ""
        self.shared_ks_tests.check_kickstart(ks_in, ks_out, expected_publish_calls=0)

    def test_no_payload_set(self):
        """Test empty string is returned when no payload is set."""
        assert self.payload_interface.ActivePayload == ""

    def test_generate_kickstart_without_payload(self):
        """Test kickstart parsing without payload set."""
        assert self.payload_interface.GenerateKickstart() == ""

    def test_process_kickstart_with_no_payload(self):
        """Test kickstart processing when no payload set or created based on KS data."""
        self.payload_interface.ReadKickstart("")
        assert self.payload_interface.ActivePayload == ""

    @patch_dbus_publish_object
    def test_create_dnf_payload(self, publisher):
        """Test creation and publishing of the DNF payload module."""
        payload_path = self.payload_interface.CreatePayload(PayloadType.DNF.value)
        assert self.payload_interface.CreatedPayloads == [payload_path]

        self.payload_interface.ActivatePayload(payload_path)
        assert self.payload_interface.ActivePayload == payload_path

        assert isinstance(PayloadContainer.from_object_path(payload_path), DNFModule)
        # DNF payload creates also Flatpak side payload so there are two publish calls
        assert publisher.call_count == 2

    @patch_dbus_publish_object
    def test_create_live_os_payload(self, publisher):
        """Test creation and publishing of the Live OS payload module."""
        payload_path = self.payload_interface.CreatePayload(PayloadType.LIVE_OS.value)
        assert self.payload_interface.CreatedPayloads == [payload_path]

        self.payload_interface.ActivatePayload(payload_path)
        assert self.payload_interface.ActivePayload == payload_path

        assert isinstance(PayloadContainer.from_object_path(payload_path), LiveOSModule)
        publisher.assert_called_once()

    @patch_dbus_publish_object
    def test_create_live_image_payload(self, publisher):
        """Test creation and publishing of the Live image payload module."""
        payload_path = self.payload_interface.CreatePayload(PayloadType.LIVE_IMAGE.value)
        assert self.payload_interface.CreatedPayloads == [payload_path]

        self.payload_interface.ActivatePayload(payload_path)
        assert self.payload_interface.ActivePayload == payload_path

        assert isinstance(PayloadContainer.from_object_path(payload_path), LiveImageModule)
        publisher.assert_called_once()

    @patch_dbus_publish_object
    def test_create_invalid_payload(self, publisher):
        """Test creation of the not existing payload."""
        with pytest.raises(ValueError):
            self.payload_interface.CreatePayload("NotAPayload")

    @patch_dbus_publish_object
    def test_create_multiple_payloads(self, publisher):
        """Test creating two payloads."""
        path_1 = self.payload_interface.CreatePayload(PayloadType.RPM_OSTREE.value)
        assert self.payload_interface.CreatedPayloads == [path_1]
        assert self.payload_interface.ActivePayload == ""

        path_2 = self.payload_interface.CreatePayload(PayloadType.LIVE_OS.value)
        assert self.payload_interface.CreatedPayloads == [path_1, path_2]
        assert self.payload_interface.ActivePayload == ""

        self.payload_interface.ActivatePayload(path_1)
        assert self.payload_interface.ActivePayload == path_1

        self.payload_interface.ActivatePayload(path_2)
        assert self.payload_interface.ActivePayload == path_2

        assert publisher.call_count == 2

    @patch_dbus_publish_object
    def test_create_live_os_source(self, publisher):
        """Test creation of the Live OS source module."""
        source_path = self.payload_interface.CreateSource(SOURCE_TYPE_LIVE_OS_IMAGE)

        check_dbus_object_creation(source_path, publisher, LiveOSSourceModule)

    @patch_dbus_publish_object
    def test_create_invalid_source(self, publisher):
        """Test creation of the not existing source."""
        with pytest.raises(ValueError):
            self.payload_interface.CreateSource("NotASource")

    def test_is_network_required(self):
        """Test the IsNetworkRequired method."""
        assert self.payload_interface.IsNetworkRequired() is False

        payload = self.payload_module.create_payload(PayloadType.DNF)
        self.payload_module.activate_payload(payload)

        assert self.payload_interface.IsNetworkRequired() is False

        source = self.payload_module.create_source(SourceType.NFS)
        payload.set_sources([source])

        assert self.payload_interface.IsNetworkRequired() is True

    def test_calculate_required_space(self):
        """Test the CalculateRequiredTest method."""
        # default
        assert self.payload_interface.CalculateRequiredSpace() == 0

        # test payload without source
        payload = self.payload_module.create_payload(PayloadType.LIVE_IMAGE)
        self.payload_module.activate_payload(payload)

        assert self.payload_interface.CalculateRequiredSpace() == 0

        # test payload with source
        source = self.payload_module.create_source(SourceType.LIVE_IMAGE)
        payload.set_sources([source])

        assert self.payload_interface.CalculateRequiredSpace() == 1024 * 1024 * 1024

        # test payload and side payload
        side_payload = Mock()
        side_payload.calculate_required_space.return_value = 1000
        payload.side_payload = side_payload

        assert self.payload_interface.CalculateRequiredSpace() == 1024 * 1024 * 1024 + 1000


    def test_get_kernel_version_list(self):
        """Test the GetKernelVersionList method."""
        assert self.payload_interface.GetKernelVersionList() == []

        payload = self.payload_module.create_payload(PayloadType.DNF)
        self.payload_module.activate_payload(payload)

        with pytest.raises(UnavailableValueError):
            self.payload_interface.GetKernelVersionList()

        payload.set_kernel_version_list(["k1", "k2", "k3"])
        assert self.payload_interface.GetKernelVersionList() == ["k1", "k2", "k3"]

    @patch_dbus_publish_object
    def test_install_with_tasks(self, publisher):
        """Test the InstallWithTasks method."""
        assert self.payload_interface.InstallWithTasks() == []

        payload = self.payload_module.create_payload(PayloadType.DNF)
        self.payload_module.activate_payload(payload)

        assert self.payload_interface.InstallWithTasks()

    @patch_dbus_publish_object
    def test_install_with_tasks_side_payload(self, publisher):
        """Test the InstallWithTasks method with a side payload."""
        task = create_autospec(Task)
        task1 = create_autospec(Task)
        task2 = create_autospec(Task)
        task3 = create_autospec(Task)

        payload = self.payload_module.create_payload(PayloadType.LIVE_IMAGE)
        with patch.object(payload, "install_with_tasks") as mock_install_with_tasks:
            mock_install_with_tasks.return_value = [task, task1]
            self.payload_module.activate_payload(payload)

            tasks_paths = self.payload_interface.InstallWithTasks()
            tasks = TaskContainer.from_object_path_list(tasks_paths)
            assert isinstance(tasks[0], PrepareSystemForInstallationTask)
            assert tasks[1:] == [task, task1]

            payload.side_payload = Mock()
            payload.side_payload.install_with_tasks.return_value = [task2, task3]

            tasks_paths = self.payload_interface.InstallWithTasks()
            tasks = TaskContainer.from_object_path_list(tasks_paths)
            assert isinstance(tasks[0], PrepareSystemForInstallationTask)
            assert tasks[1:] == [task, task1, task2, task3]


    @patch_dbus_publish_object
    def test_post_install_with_tasks(self, publisher):
        """Test the PostInstallWithTasks method."""
        assert self.payload_interface.PostInstallWithTasks() == []

        payload = self.payload_module.create_payload(PayloadType.DNF)
        self.payload_module.activate_payload(payload)

        assert self.payload_interface.PostInstallWithTasks()

    @patch_dbus_publish_object
    def test_post_install_with_tasks_side_payload(self, publisher):
        """Test the PostInstallWithTasks method with a side payload."""
        task = create_autospec(Task)
        task1 = create_autospec(Task)
        task2 = create_autospec(Task)
        task3 = create_autospec(Task)

        payload = self.payload_module.create_payload(PayloadType.LIVE_IMAGE)
        with patch.object(payload, "post_install_with_tasks") as mock_install_with_tasks:
            mock_install_with_tasks.return_value = [task, task1]
            self.payload_module.activate_payload(payload)

            tasks_paths = self.payload_interface.PostInstallWithTasks()
            tasks = TaskContainer.from_object_path_list(tasks_paths)
            assert isinstance(tasks[0], CopyDriverDisksFilesTask)
            assert tasks[1:] == [task, task1]

            payload.side_payload = Mock()
            payload.side_payload.post_install_with_tasks.return_value = [task2, task3]

            tasks_paths = self.payload_interface.PostInstallWithTasks()
            tasks = TaskContainer.from_object_path_list(tasks_paths)
            assert isinstance(tasks[0], CopyDriverDisksFilesTask)
            assert tasks[1:] == [task, task1, task2, task3]

    @patch_dbus_publish_object
    def test_tear_down_with_tasks(self, publisher):
        """Test the TeardownWithTasks method."""
        assert self.payload_interface.TeardownWithTasks() == []

        payload = self.payload_module.create_payload(PayloadType.DNF)
        self.payload_module.activate_payload(payload)

        source = self.payload_module.create_source(SourceType.CDROM)
        payload.set_sources([source])

        publisher.reset_mock()
        assert self.payload_interface.TeardownWithTasks()

    @patch_dbus_publish_object
    def test_tear_down_with_tasks_side_payload(self, publisher):
        """Test the TeardownWithTasks method with a side payload."""
        task = create_autospec(Task)
        task1 = create_autospec(Task)
        task2 = create_autospec(Task)
        task3 = create_autospec(Task)

        payload = self.payload_module.create_payload(PayloadType.LIVE_IMAGE)
        with patch.object(payload, "tear_down_with_tasks") as mock_install_with_tasks:
            mock_install_with_tasks.return_value = [task, task1]
            self.payload_module.activate_payload(payload)

            tasks_paths = self.payload_interface.TeardownWithTasks()
            tasks = TaskContainer.from_object_path_list(tasks_paths)
            assert tasks == [task, task1]

            payload.side_payload = Mock()
            payload.side_payload.tear_down_with_tasks.return_value = [task2, task3]

            tasks_paths = self.payload_interface.TeardownWithTasks()
            tasks = TaskContainer.from_object_path_list(tasks_paths)
            assert tasks == [task, task1, task2, task3]


class PrepareSystemForInstallationTaskTestCase(TestCase):

    def test_run(self):
        """Run the PrepareSystemForInstallationTask task."""
        with TemporaryDirectory() as sysroot:
            task = PrepareSystemForInstallationTask(sysroot=sysroot)
            task.run()

            root_dir = os.path.join(sysroot, "/root")
            assert os.path.isdir(root_dir)

    @patch('pyanaconda.modules.payloads.installation.kernel_arguments', {})
    def test_run_without_denylist(self):
        """Run the task without a denylist."""
        with TemporaryDirectory() as sysroot:
            task = PrepareSystemForInstallationTask(sysroot=sysroot)
            task.run()

            denylist_file = os.path.join(sysroot, "etc/modprobe.d/anaconda-denylist.conf")
            assert not os.path.isfile(denylist_file)

    @patch('pyanaconda.modules.payloads.installation.kernel_arguments',
           {"modprobe.blacklist": "mod1 mod2 nonono_mod"})
    def test_run_with_denylist(self):
        """Run the task with a denylist."""
        expected_content = dedent("""
         # Module denylist written by anaconda
         blacklist mod1
         blacklist mod2
         blacklist nonono_mod
         """).lstrip()

        with TemporaryDirectory() as sysroot:
            task = PrepareSystemForInstallationTask(sysroot=sysroot)
            task.run()

            denylist_file = os.path.join(sysroot, "etc/modprobe.d/anaconda-denylist.conf")
            assert os.path.isfile(denylist_file)

            with open(denylist_file, "rt") as f:
                assert expected_content == f.read()


class PayloadSharedTasksTest(TestCase):

    def test_set_up_sources_task(self):
        """Test task to set up installation sources."""
        called_position = []

        def save_position(name):
            called_position.append(name)
            return DEFAULT

        set_up_task1 = create_autospec(Task)
        set_up_task2 = create_autospec(Task)
        set_up_task3 = create_autospec(Task)

        set_up_task1.run_with_signals.side_effect = lambda: save_position("task1")
        set_up_task2.run_with_signals.side_effect = lambda: save_position("task2")
        set_up_task3.run_with_signals.side_effect = lambda: save_position("task3")

        source1 = create_autospec(PayloadSourceBase)
        source2 = create_autospec(PayloadSourceBase)

        source1.set_up_with_tasks.side_effect = lambda: save_position("source1")
        source1.set_up_with_tasks.return_value = [set_up_task1, set_up_task2]
        source2.set_up_with_tasks.side_effect = lambda: save_position("source2")
        source2.set_up_with_tasks.return_value = [set_up_task3]

        task = SetUpSourcesTask([source1, source2])

        task.run()

        source1.set_up_with_tasks.assert_called_once()
        source2.set_up_with_tasks.assert_called_once()
        set_up_task1.run_with_signals.assert_called_once()
        set_up_task2.run_with_signals.assert_called_once()
        set_up_task3.run_with_signals.assert_called_once()
        assert ["source1", "task1", "task2", "source2", "task3"] == called_position

    def test_set_up_sources_task_without_sources(self):
        """Test task to set up installation sources without sources set."""
        task = SetUpSourcesTask([])

        with pytest.raises(SourceSetupError):
            task.run()

    def test_set_up_sources_task_with_exception(self):
        """Test task to set up installation sources which raise exception."""
        set_up_task1 = create_autospec(Task)
        set_up_task2 = create_autospec(Task)
        set_up_task3 = create_autospec(Task)

        set_up_task2.run_with_signals.side_effect = SourceSetupError("task2 error")

        source1 = create_autospec(PayloadSourceBase)
        source2 = create_autospec(PayloadSourceBase)

        source1.set_up_with_tasks.return_value = [set_up_task1, set_up_task2]
        source2.set_up_with_tasks.return_value = [set_up_task3]

        task = SetUpSourcesTask([source1, source2])

        with pytest.raises(SourceSetupError):
            task.run()

        set_up_task1.run_with_signals.assert_called_once()
        set_up_task2.run_with_signals.assert_called_once()
        set_up_task3.run_with_signals.assert_not_called()

    def test_tear_down_sources_task(self):
        """Test task to tear down installation sources."""
        called_position = []

        def save_position(name):
            called_position.append(name)
            return DEFAULT

        tear_down_task1 = create_autospec(Task)
        tear_down_task2 = create_autospec(Task)
        tear_down_task3 = create_autospec(Task)

        tear_down_task1.run.side_effect = lambda: save_position("task1")
        tear_down_task2.run.side_effect = lambda: save_position("task2")
        tear_down_task3.run.side_effect = lambda: save_position("task3")

        source1 = create_autospec(PayloadSourceBase)
        source2 = create_autospec(PayloadSourceBase)

        source1.tear_down_with_tasks.side_effect = lambda: save_position("source1")
        source1.tear_down_with_tasks.return_value = [tear_down_task1, tear_down_task2]
        source2.tear_down_with_tasks.side_effect = lambda: save_position("source2")
        source2.tear_down_with_tasks.return_value = [tear_down_task3]

        task = TearDownSourcesTask([source1, source2])

        task.run()

        source1.tear_down_with_tasks.assert_called_once()
        source2.tear_down_with_tasks.assert_called_once()
        tear_down_task1.run.assert_called_once()
        tear_down_task2.run.assert_called_once()
        tear_down_task3.run.assert_called_once()
        assert ["source1", "task1", "task2", "source2", "task3"] == called_position

    def test_tear_down_sources_task_without_sources(self):
        """Test task to tear down installation sources without sources set."""
        task = TearDownSourcesTask([])

        with pytest.raises(SourceSetupError):
            task.run()

    def test_tear_down_sources_task_error_processing(self):
        """Test error processing task to tear down installation sources."""
        tear_down_task1 = create_autospec(Task)
        tear_down_task2 = create_autospec(Task)
        tear_down_task3 = create_autospec(Task)

        tear_down_task1.run.side_effect = SourceTearDownError("task1 error")
        tear_down_task3.run.side_effect = SourceTearDownError("task3 error")

        source1 = create_autospec(PayloadSourceBase)
        source2 = create_autospec(PayloadSourceBase)

        source1.tear_down_with_tasks.return_value = [tear_down_task1, tear_down_task2]
        source2.tear_down_with_tasks.return_value = [tear_down_task3]

        task = TearDownSourcesTask([source1, source2])

        with self.assertLogs(level="ERROR") as cm:
            with pytest.raises(SourceTearDownError):
                task.run()

            assert any(map(lambda x: "task1 error" in x, cm.output))
            assert any(map(lambda x: "task3 error" in x, cm.output))

        # all the tasks should be tear down even when exception raised
        tear_down_task1.run.assert_called_once()
        tear_down_task2.run.assert_called_once()
        tear_down_task3.run.assert_called_once()
