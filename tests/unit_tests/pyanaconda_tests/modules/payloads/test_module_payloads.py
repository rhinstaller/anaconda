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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Jiri Konecny <jkonecny@redhat.com>
#
import pytest

from unittest import TestCase
from unittest.mock import patch, create_autospec, DEFAULT

from pyanaconda.core.constants import SOURCE_TYPE_LIVE_OS_IMAGE
from tests.unit_tests.pyanaconda_tests import patch_dbus_publish_object, check_dbus_object_creation
from tests.unit_tests.pyanaconda_tests.modules.payloads.payload.module_payload_shared import PayloadKickstartSharedTest

from pyanaconda.modules.common.containers import PayloadContainer
from pyanaconda.modules.common.errors.payload import SourceSetupError, SourceTearDownError
from pyanaconda.modules.common.task import Task
from pyanaconda.modules.payloads.source.source_base import PayloadSourceBase
from pyanaconda.modules.payloads.base.initialization import PrepareSystemForInstallationTask, \
    SetUpSourcesTask, TearDownSourcesTask
from pyanaconda.modules.payloads.constants import PayloadType
from pyanaconda.modules.payloads.payloads_interface import PayloadsInterface
from pyanaconda.modules.payloads.payloads import PayloadsService
from pyanaconda.modules.payloads.payload.dnf.dnf import DNFModule
from pyanaconda.modules.payloads.payload.live_image.live_image import LiveImageModule
from pyanaconda.modules.payloads.payload.live_os.live_os import LiveOSModule
from pyanaconda.modules.payloads.source.live_os.live_os import LiveOSSourceModule


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
            "nfs",
            "ostreecontainer",
            "ostreesetup",
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
        publisher.assert_called_once()

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
        path_1 = self.payload_interface.CreatePayload(PayloadType.DNF.value)
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


class PayloadSharedTasksTest(TestCase):

    @patch('pyanaconda.modules.payloads.base.initialization.write_module_blacklist')
    @patch('pyanaconda.modules.payloads.base.initialization.create_root_dir')
    def test_prepare_system_for_install_task(self, create_root_dir_mock,
                                             write_module_blacklist_mock):
        """Test task prepare system for installation."""
        # the dir won't be used because of mock
        task = PrepareSystemForInstallationTask("/some/dir")

        task.run()

        create_root_dir_mock.assert_called_once()
        write_module_blacklist_mock.assert_called_once()

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
