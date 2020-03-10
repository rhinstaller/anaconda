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
import os

from unittest import TestCase
from unittest.mock import patch, Mock, create_autospec, DEFAULT
from textwrap import dedent
from tempfile import TemporaryDirectory

from pyanaconda.core.kickstart.specification import KickstartSpecificationHandler, \
    KickstartSpecificationParser
from pyanaconda.modules.payloads.kickstart import PayloadKickstartSpecification
from pyanaconda.modules.payloads.payload.payload_base import PayloadBase
from pyanaconda.modules.payloads.payload.payload_base_interface import PayloadBaseInterface
from pyanaconda.modules.payloads.source.source_base_interface import PayloadSourceBaseInterface
from tests.nosetests.pyanaconda_tests import patch_dbus_publish_object, check_dbus_object_creation
from pyanaconda.modules.common.containers import PayloadContainer
from pyanaconda.modules.common.errors.payload import SourceSetupError, SourceTearDownError, \
    PayloadNotSetError
from pyanaconda.modules.common.task import Task
from pyanaconda.modules.payloads.source.source_base import PayloadSourceBase
from pyanaconda.modules.payloads.base.utils import create_root_dir, write_module_blacklist, \
    get_dir_size
from pyanaconda.modules.payloads.base.initialization import PrepareSystemForInstallationTask, \
    SetUpSourcesTask, TearDownSourcesTask
from pyanaconda.modules.payloads.factory import PayloadFactory, SourceFactory
from pyanaconda.modules.payloads.constants import PayloadType, SourceType
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

    def kickstart_properties_test(self):
        """Test kickstart properties."""
        self.assertEqual(self.payload_interface.KickstartCommands, ['liveimg'])
        self.assertEqual(self.payload_interface.KickstartSections, ["packages"])
        self.assertEqual(self.payload_interface.KickstartAddons, [])

    def no_payload_set_test(self):
        """Test empty string is returned when no payload is set."""
        with self.assertRaises(PayloadNotSetError):
            self.payload_interface.GetActivePayload()

    def generate_kickstart_without_payload_test(self):
        """Test kickstart parsing without payload set."""
        self.assertEqual(self.payload_interface.GenerateKickstart(), "")

    def process_kickstart_with_no_payload_test(self):
        """Test kickstart processing when no payload set or created based on KS data."""
        self.payload_interface.ReadKickstart("")

        with self.assertRaises(PayloadNotSetError):
            self.payload_interface.GetActivePayload()

    @patch_dbus_publish_object
    def is_payload_set_test(self, publisher):
        """Test IsPayloadSet API."""
        self.assertFalse(self.payload_interface.IsPayloadSet())

        self.payload_interface.CreatePayload(PayloadType.DNF.value)
        self.assertTrue(self.payload_interface.IsPayloadSet())

    @patch_dbus_publish_object
    def create_dnf_payload_test(self, publisher):
        """Test creation and publishing of the DNF payload module."""
        payload_path = self.payload_interface.CreatePayload(PayloadType.DNF.value)
        self.assertEqual(self.payload_interface.GetActivePayload(), payload_path)
        self.assertIsInstance(PayloadContainer.from_object_path(payload_path), DNFModule)
        publisher.assert_called_once()

    @patch_dbus_publish_object
    def create_live_os_payload_test(self, publisher):
        """Test creation and publishing of the Live OS payload module."""
        payload_path = self.payload_interface.CreatePayload(PayloadType.LIVE_OS.value)
        self.assertEqual(self.payload_interface.GetActivePayload(), payload_path)
        self.assertIsInstance(PayloadContainer.from_object_path(payload_path), LiveOSModule)
        publisher.assert_called_once()

    @patch_dbus_publish_object
    def create_live_image_payload_test(self, publisher):
        """Test creation and publishing of the Live image payload module."""
        payload_path = self.payload_interface.CreatePayload(PayloadType.LIVE_IMAGE.value)
        self.assertEqual(self.payload_interface.GetActivePayload(), payload_path)
        self.assertIsInstance(PayloadContainer.from_object_path(payload_path), LiveImageModule)
        publisher.assert_called_once()

    @patch_dbus_publish_object
    def create_invalid_payload_test(self, publisher):
        """Test creation of the not existing payload."""
        with self.assertRaises(ValueError):
            self.payload_interface.CreatePayload("NotAPayload")

    @patch_dbus_publish_object
    def create_multiple_payloads_test(self, publisher):
        """Test creating two payloads."""
        self.payload_interface.CreatePayload(PayloadType.DNF.value)
        path = self.payload_interface.CreatePayload(PayloadType.LIVE_OS.value)

        # The last one should win
        self.assertEqual(self.payload_interface.GetActivePayload(), path)
        self.assertEqual(publisher.call_count, 2)

    @patch_dbus_publish_object
    def create_live_os_source_test(self, publisher):
        """Test creation of the Live OS source module."""
        source_path = self.payload_interface.CreateSource(SourceType.LIVE_OS_IMAGE.value)

        check_dbus_object_creation(self, source_path, publisher, LiveOSSourceModule)

    @patch_dbus_publish_object
    def create_invalid_source_test(self, publisher):
        """Test creation of the not existing source."""
        with self.assertRaises(ValueError):
            self.payload_interface.CreateSource("NotASource")


class PayloadSharedTasksTest(TestCase):

    @patch('pyanaconda.modules.payloads.base.initialization.write_module_blacklist')
    @patch('pyanaconda.modules.payloads.base.initialization.create_root_dir')
    def prepare_system_for_install_task_test(self, create_root_dir_mock,
                                             write_module_blacklist_mock):
        """Test task prepare system for installation."""
        # the dir won't be used because of mock
        task = PrepareSystemForInstallationTask("/some/dir")

        task.run()

        create_root_dir_mock.assert_called_once()
        write_module_blacklist_mock.assert_called_once()

    def set_up_sources_task_test(self):
        """Test task to set up installation sources."""
        called_position = []

        def save_position(name):
            called_position.append(name)
            return DEFAULT

        set_up_task1 = create_autospec(Task)
        set_up_task2 = create_autospec(Task)
        set_up_task3 = create_autospec(Task)

        set_up_task1.run.side_effect = lambda: save_position("task1")
        set_up_task2.run.side_effect = lambda: save_position("task2")
        set_up_task3.run.side_effect = lambda: save_position("task3")

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
        set_up_task1.run.assert_called_once()
        set_up_task2.run.assert_called_once()
        set_up_task3.run.assert_called_once()
        self.assertEqual(["source1", "task1", "task2", "source2", "task3"], called_position)

    def set_up_sources_task_without_sources_test(self):
        """Test task to set up installation sources without sources set."""
        task = SetUpSourcesTask([])

        with self.assertRaises(SourceSetupError):
            task.run()

    def set_up_sources_task_with_exception_test(self):
        """Test task to set up installation sources which raise exception."""
        set_up_task1 = create_autospec(Task)
        set_up_task2 = create_autospec(Task)
        set_up_task3 = create_autospec(Task)

        set_up_task2.run.side_effect = SourceSetupError("task2 error")

        source1 = create_autospec(PayloadSourceBase)
        source2 = create_autospec(PayloadSourceBase)

        source1.set_up_with_tasks.return_value = [set_up_task1, set_up_task2]
        source2.set_up_with_tasks.return_value = [set_up_task3]

        task = SetUpSourcesTask([source1, source2])

        with self.assertRaises(SourceSetupError):
            task.run()

        set_up_task1.run.assert_called_once()
        set_up_task2.run.assert_called_once()
        set_up_task3.run.assert_not_called()

    def tear_down_sources_task_test(self):
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
        self.assertEqual(["source1", "task1", "task2", "source2", "task3"], called_position)

    def tear_down_sources_task_without_sources_test(self):
        """Test task to tear down installation sources without sources set."""
        task = TearDownSourcesTask([])

        with self.assertRaises(SourceSetupError):
            task.run()

    def tear_down_sources_task_error_processing_test(self):
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
            with self.assertRaises(SourceTearDownError):
                task.run()

            self.assertTrue(any(map(lambda x: "task1 error" in x, cm.output)))
            self.assertTrue(any(map(lambda x: "task3 error" in x, cm.output)))

        # all the tasks should be tear down even when exception raised
        tear_down_task1.run.assert_called_once()
        tear_down_task2.run.assert_called_once()
        tear_down_task3.run.assert_called_once()


class PayloadSharedUtilsTest(TestCase):

    def create_root_test(self):
        """Test payload create root directory function."""
        with TemporaryDirectory() as temp:
            create_root_dir(temp)

            root_dir = os.path.join(temp, "/root")

            self.assertTrue(os.path.isdir(root_dir))

    @patch('pyanaconda.modules.payloads.base.utils.kernel_arguments',
           {"modprobe.blacklist": "mod1 mod2 nonono_mod"})
    def write_module_blacklist_test(self):
        """Test write kernel module blacklist to the install root."""
        with TemporaryDirectory() as temp:
            write_module_blacklist(temp)

            blacklist_file = os.path.join(temp, "etc/modprobe.d/anaconda-blacklist.conf")

            self.assertTrue(os.path.isfile(blacklist_file))

            with open(blacklist_file, "rt") as f:
                expected_content = """
                # Module blacklists written by anaconda
                blacklist mod1
                blacklist mod2
                blacklist nonono_mod
                """
                self.assertEqual(dedent(expected_content).lstrip(), f.read())

    @patch('pyanaconda.modules.payloads.base.utils.kernel_arguments', {})
    def write_empty_module_blacklist_test(self):
        """Test write kernel module blacklist to the install root -- empty list."""
        with TemporaryDirectory() as temp:
            write_module_blacklist(temp)

            blacklist_file = os.path.join(temp, "etc/modprobe.d/anaconda-blacklist.conf")

            self.assertFalse(os.path.isfile(blacklist_file))

    def get_dir_size_test(self):
        """Test the get_dir_size function."""

        # dev null should have a size == 0
        self.assertEqual(get_dir_size('/dev/null'), 0)

        # incorrect path should also return 0
        self.assertEqual(get_dir_size('/dev/null/foo'), 0)

        # check if an int is always returned
        self.assertIsInstance(get_dir_size('/dev/null'), int)
        self.assertIsInstance(get_dir_size('/dev/null/foo'), int)

        # TODO: mock some dirs and check if their size is
        # computed correctly


class FactoryTestCase(TestCase):

    def create_payload_test(self):
        """Test PayloadFactory create method."""
        for payload_type in PayloadType:
            module = PayloadFactory.create(payload_type)
            self.assertIsInstance(module, PayloadBase)
            self.assertIsInstance(module.for_publication(), PayloadBaseInterface)
            self.assertEqual(module.type, payload_type)

    def create_payload_from_ks_test(self):
        """Test PayloadFactory create from KS method."""
        self._check_payload_type(
            PayloadType.LIVE_IMAGE,
            "liveimg --url http://my/path"
        )
        self._check_payload_type(
            PayloadType.DNF,
            "%packages\na\nb\nc\n%end"
        )
        self._check_payload_type(
            None,
            ""
        )

    def _check_payload_type(self, payload_type, kickstart):
        """Check the payload type for the given kickstart."""
        specification = PayloadKickstartSpecification
        handler = KickstartSpecificationHandler(specification)
        parser = KickstartSpecificationParser(handler, specification)
        parser.readKickstartFromString(kickstart)
        self.assertEqual(payload_type, PayloadFactory.get_type_for_kickstart(handler))

    def failed_create_payload_test(self):
        """Test failed create method of the payload factory."""
        with self.assertRaises(ValueError):
            PayloadFactory.create("INVALID")

    def create_source_test(self):
        """Test SourceFactory create method."""
        for source_type in SourceType:
            module = SourceFactory.create(source_type)
            self.assertIsInstance(module, PayloadSourceBase)
            self.assertIsInstance(module.for_publication(), PayloadSourceBaseInterface)
            self.assertEqual(module.type, source_type)

    def failed_create_source_test(self):
        """Test failed create method of the source factory."""
        with self.assertRaises(ValueError):
            SourceFactory.create("INVALID")
