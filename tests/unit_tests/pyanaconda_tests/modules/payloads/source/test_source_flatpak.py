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
from tempfile import TemporaryDirectory
from unittest.mock import patch

from pyanaconda.core.constants import SOURCE_TYPE_FLATPAK
from pyanaconda.modules.common.constants.interfaces import PAYLOAD_SOURCE_RPM_OSTREE
from pyanaconda.modules.payloads.constants import SourceState, SourceType
from pyanaconda.modules.payloads.source.flatpak.flatpak import FlatpakSourceModule
from pyanaconda.modules.payloads.source.flatpak.initialization import (
    GetFlatpaksSizeTask,
)
from tests.unit_tests.pyanaconda_tests import check_dbus_property


class FlatpakSourceInterfaceTestCase(unittest.TestCase):
    """Test the DBus interface of the Flatpak source."""

    def setUp(self):
        self.module = FlatpakSourceModule()
        self.interface = self.module.for_publication()

    def _check_dbus_property(self, *args, **kwargs):
        check_dbus_property(
            PAYLOAD_SOURCE_RPM_OSTREE,
            self.interface,
            *args, **kwargs
        )

    def test_type(self):
        """Test the Type property."""
        assert self.interface.Type == SOURCE_TYPE_FLATPAK

    def test_description(self):
        """Test the Description property."""
        assert self.interface.Description == "Flatpak"

    def test_is_available(self):
        """Test the IsAvailable method."""
        assert self.interface.IsAvailable() is False


class FlatpakSourceTestCase(unittest.TestCase):
    """Test the OSTree source module."""

    def setUp(self):
        self.module = FlatpakSourceModule()

    def test_type(self):
        """Test the type property."""
        assert self.module.type == SourceType.FLATPAK

    def test_network_required(self):
        """Test the network_required property."""
        assert self.module.network_required is False

    def test_required_space(self):
        """Test the required_space property."""
        assert self.module.required_space == 0

        self.module._set_required_space(1024)
        assert self.module.required_space == 1024

    @patch("pyanaconda.modules.payloads.source.flatpak.flatpak.GetFlatpaksSizeTask.run")
    def test_set_required_space_with_task(self, run_mock):
        """Set the required_space property with a task."""
        run_mock.return_value = 1024

        for task in self.module.set_up_with_tasks():
            task.run_with_signals()

        assert self.module.required_space == 1024

    def test_get_state(self):
        """Test the source state."""
        assert self.module.get_state() == SourceState.NOT_APPLICABLE

    def test_set_up_with_tasks(self):
        """Test the set-up tasks."""
        tasks = self.module.set_up_with_tasks()

        assert len(tasks) == 1
        assert isinstance(tasks[0], GetFlatpaksSizeTask)

    def test_tear_down_with_tasks(self):
        """Test the tear-down tasks."""
        assert self.module.tear_down_with_tasks() == []

    def test_repr(self):
        """Test the string representation."""
        assert repr(self.module) == "Source(type='FLATPAK')"


class GetFlatpaksSizeTaskTest(unittest.TestCase):

    @patch("pyanaconda.modules.payloads.source.flatpak.initialization.FlatpakManager")
    def test_run_success(self, fm_mock):
        """Test GetFlatpaksSizeTask"""
        fm_instance = fm_mock.return_value
        fm_instance.get_required_size.return_value = 123456789

        with TemporaryDirectory() as temp:
            task = GetFlatpaksSizeTask(temp)
            result = task.run()
            assert isinstance(result, int)
            assert result == 123456789

        fm_instance.initialize_with_path.assert_called_once_with("/var/tmp/anaconda-flatpak-temp")
        fm_instance.get_required_size.assert_called_once()
        fm_instance.cleanup.assert_called_once()
