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

from tests.nosetests.pyanaconda_tests import patch_dbus_publish_object, check_dbus_object_creation
from pyanaconda.modules.common.constants.objects import PAYLOAD_DEFAULT, LIVE_OS_HANDLER, \
    LIVE_IMAGE_HANDLER
from pyanaconda.modules.common.errors.payload import SourceSetupError, SourceTearDownError
from pyanaconda.modules.common.task import Task
from pyanaconda.modules.payload.sources.source_base import PayloadSourceBase
from pyanaconda.modules.payload.base.utils import create_root_dir, write_module_blacklist, \
    get_dir_size
from pyanaconda.modules.payload.base.initialization import PrepareSystemForInstallationTask, \
    SetUpSourcesTask, TearDownSourcesTask
from pyanaconda.modules.payload.factory import HandlerFactory, SourceFactory
from pyanaconda.modules.payload.constants import PayloadType, SourceType
from pyanaconda.modules.payload.payload_interface import PayloadInterface
from pyanaconda.modules.payload.payload import PayloadService
from pyanaconda.modules.payload.payloads.dnf.dnf import DNFHandlerModule
from pyanaconda.modules.payload.payloads.live_image.live_image import LiveImageHandlerModule
from pyanaconda.modules.payload.payloads.live_os.live_os import LiveOSHandlerModule
from pyanaconda.modules.payload.sources.live_os.live_os import LiveOSSourceModule


class PayloadInterfaceTestCase(TestCase):

    def setUp(self):
        """Set up the payload module."""
        self.payload_module = PayloadService()
        self.payload_interface = PayloadInterface(self.payload_module)

    def kickstart_properties_test(self):
        """Test kickstart properties."""
        self.assertEqual(self.payload_interface.KickstartCommands, ['liveimg'])
        self.assertEqual(self.payload_interface.KickstartSections, ["packages"])
        self.assertEqual(self.payload_interface.KickstartAddons, [])

    def no_handler_set_test(self):
        """Test empty string is returned when no handler is set."""
        self.assertEqual(self.payload_interface.GetActiveHandlerPath(), "")

    def generate_kickstart_without_handler_test(self):
        """Test kickstart parsing without handler set."""
        self.assertEqual(self.payload_interface.GenerateKickstart(), "")

    def process_kickstart_with_no_handler_test(self):
        """Test kickstart processing when no handler set or created based on KS data."""
        with self.assertLogs('anaconda.modules.payload.payload', level="WARNING") as log:
            self.payload_interface.ReadKickstart("")

            self.assertTrue(any(map(lambda x: "No payload was created" in x, log.output)))

    @patch_dbus_publish_object
    def is_handler_set_test(self, publisher):
        """Test IsHandlerSet API."""
        self.assertFalse(self.payload_interface.IsHandlerSet())

        self.payload_interface.CreateHandler(PayloadType.DNF.value)
        self.assertTrue(self.payload_interface.IsHandlerSet())

    @patch_dbus_publish_object
    def create_dnf_handler_test(self, publisher):
        """Test creation and publishing of the DNF handler module."""
        self.payload_interface.CreateHandler(PayloadType.DNF.value)
        self.assertEqual(self.payload_interface.GetActiveHandlerPath(),
                         PAYLOAD_DEFAULT.object_path)
        # here the publisher is called twice because the Packages section is also published
        self.assertEqual(publisher.call_count, 2)

    @patch_dbus_publish_object
    def create_live_os_handler_test(self, publisher):
        """Test creation and publishing of the Live OS handler module."""
        self.payload_interface.CreateHandler(PayloadType.LIVE_OS.value)
        self.assertEqual(self.payload_interface.GetActiveHandlerPath(),
                         LIVE_OS_HANDLER.object_path)
        publisher.assert_called_once()

    @patch_dbus_publish_object
    def create_live_image_handler_test(self, publisher):
        """Test creation and publishing of the Live image handler module."""
        self.payload_interface.CreateHandler(PayloadType.LIVE_IMAGE.value)
        self.assertEqual(self.payload_interface.GetActiveHandlerPath(),
                         LIVE_IMAGE_HANDLER.object_path)
        publisher.assert_called_once()

    @patch_dbus_publish_object
    def create_invalid_handler_test(self, publisher):
        """Test creation of the not existing handler."""
        with self.assertRaises(ValueError):
            self.payload_interface.CreateHandler("NotAHandler")

    @patch_dbus_publish_object
    def create_multiple_handlers_test(self, publisher):
        """Test creating two handlers."""
        self.payload_interface.CreateHandler(PayloadType.DNF.value)
        self.payload_interface.CreateHandler(PayloadType.LIVE_OS.value)

        # The last one should win
        self.assertEqual(self.payload_interface.GetActiveHandlerPath(),
                         LIVE_OS_HANDLER.object_path)
        self.assertEqual(publisher.call_count, 3)

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

    @patch('pyanaconda.modules.payload.base.initialization.write_module_blacklist')
    @patch('pyanaconda.modules.payload.base.initialization.create_root_dir')
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

    @patch('pyanaconda.modules.payload.base.utils.flags')
    def write_module_blacklist_test(self, flags):
        """Test write kernel module blacklist to the install root."""
        with TemporaryDirectory() as temp:
            flags.cmdline = {"modprobe.blacklist": "mod1 mod2 nonono_mod"}

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

    @patch('pyanaconda.modules.payload.base.utils.flags')
    def write_empty_module_blacklist_test(self, flags):
        """Test write kernel module blacklist to the install root -- empty list."""
        with TemporaryDirectory() as temp:
            flags.cmdline = {}

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

    def create_handler_test(self):
        """Test HandlerFactory create method."""
        self.assertIsInstance(HandlerFactory.create(PayloadType.DNF),
                              DNFHandlerModule)
        self.assertIsInstance(HandlerFactory.create(PayloadType.LIVE_IMAGE),
                              LiveImageHandlerModule)
        self.assertIsInstance(HandlerFactory.create(PayloadType.LIVE_OS),
                              LiveOSHandlerModule)

    def create_handler_from_ks_test(self):
        """Test HandlerFactory create from KS method."""
        # Live OS can't be detected from the KS data so it is not tested here
        data = Mock()
        data.liveimg.seen = True
        data.packages.seen = False

        self.assertIsInstance(HandlerFactory.create_from_ks_data(data),
                              LiveImageHandlerModule)

        data.liveimg.seen = False
        data.packages.seen = True
        self.assertIsInstance(HandlerFactory.create_from_ks_data(data),
                              DNFHandlerModule)

        data.liveimg.seen = False
        data.packages.seen = False
        self.assertIsNone(HandlerFactory.create_from_ks_data(data))

    def create_source_test(self):
        """Test SourceFactory create method."""
        self.assertIsInstance(SourceFactory.create(SourceType.LIVE_OS_IMAGE),
                              LiveOSSourceModule)
