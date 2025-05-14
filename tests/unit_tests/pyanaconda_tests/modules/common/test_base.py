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
import warnings

from dasbus.typing import *  # pylint: disable=wildcard-import
from pykickstart.errors import (
    KickstartDeprecationWarning,
    KickstartParseError,
    KickstartParseWarning,
)

from pyanaconda.modules.common.base import KickstartModuleInterface, KickstartService
from pyanaconda.modules.common.task import Task
from tests.unit_tests.pyanaconda_tests import (
    check_task_creation_list,
    patch_dbus_publish_object,
)


class BaseModuleTestCase(unittest.TestCase):
    """Test base classes for DBus modules."""

    def setUp(self):
        self.maxDiff = None

    def test_read_kickstart_error(self):
        """Test ReadKickstart with a custom error."""

        class Service(KickstartService):
            def process_kickstart(self, data):
                raise KickstartParseError("Error!")

        module = Service()
        interface = KickstartModuleInterface(module)

        error = {
            'file-name': get_variant(Str, ""),
            'line-number': get_variant(UInt32, 0),
            'message': get_variant(Str, 'Error!'),
            'module-name': get_variant(Str, ""),
        }

        report = {
            'error-messages': get_variant(List[Structure], [error]),
            'warning-messages': get_variant(List[Structure], [])
        }

        assert interface.ReadKickstart("") == report

    def test_read_kickstart_error_line_number(self):
        """Test ReadKickstart with a custom error on a specified line."""

        class Service(KickstartService):
            def process_kickstart(self, data):
                raise KickstartParseError("Error!", lineno=10)

        module = Service()
        interface = KickstartModuleInterface(module)

        error = {
            'file-name': get_variant(Str, ""),
            'line-number': get_variant(UInt32, 10),
            'message': get_variant(Str, 'Error!'),
            'module-name': get_variant(Str, ""),
        }

        report = {
            'error-messages': get_variant(List[Structure], [error]),
            'warning-messages': get_variant(List[Structure], [])
        }

        assert interface.ReadKickstart("") == report

    def test_read_kickstart_warning(self):
        """Test ReadKickstart with a custom warning."""

        class Service(KickstartService):
            def process_kickstart(self, data):
                warnings.warn("First warning!", KickstartParseWarning)
                warnings.warn("Other warning!", DeprecationWarning)
                warnings.warn("Second warning!", KickstartDeprecationWarning)

        module = Service()
        interface = KickstartModuleInterface(module)

        first_warning = {
            'file-name': get_variant(Str, ""),
            'line-number': get_variant(UInt32, 0),
            'message': get_variant(Str, 'First warning!'),
            'module-name': get_variant(Str, ""),
        }

        second_warning = {
            'file-name': get_variant(Str, ""),
            'line-number': get_variant(UInt32, 0),
            'message': get_variant(Str, 'Second warning!'),
            'module-name': get_variant(Str, ""),
        }

        report = {
            'error-messages': get_variant(List[Structure], []),
            'warning-messages': get_variant(List[Structure], [first_warning, second_warning])
        }

        assert interface.ReadKickstart("") == report

    def test_default_configure_bootloader_with_tasks(self):
        """Test the ConfigureBootloaderWithTasks method with defaults."""
        service = KickstartService()
        interface = KickstartModuleInterface(service)

        tasks = interface.ConfigureBootloaderWithTasks(["1", "2", "3"])
        assert tasks == []

    @patch_dbus_publish_object
    def test_configure_bootloader_with_tasks(self, publisher):
        """Test the ConfigureBootloaderWithTasks method."""
        class Task1(Task):

            @property
            def name(self):
                """The name of the task."""
                return "Task 1"

            def run(self):
                """Nothing to do."""

        class Service(KickstartService):
            def configure_bootloader_with_tasks(self, kernel_versions):
                """Return a list of installation tasks."""
                return [Task1()]

        service = Service()
        interface = KickstartModuleInterface(service)

        tasks = interface.ConfigureBootloaderWithTasks(["1", "2", "3"])
        check_task_creation_list(tasks, publisher, [Task1])
