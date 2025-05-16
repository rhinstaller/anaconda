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
from unittest.mock import Mock, patch

import pytest
from blivet.size import Size

from pyanaconda.core.constants import PAYLOAD_TYPE_FLATPAK
from pyanaconda.modules.common.constants.interfaces import PAYLOAD_FLATPAK
from pyanaconda.modules.common.errors.general import UnavailableValueError
from pyanaconda.modules.common.structures.payload import RepoConfigurationData
from pyanaconda.modules.payloads.constants import SourceType
from pyanaconda.modules.payloads.payload.flatpak.flatpak import FlatpakModule
from pyanaconda.modules.payloads.payload.flatpak.flatpak_interface import (
    FlatpakInterface,
)
from pyanaconda.modules.payloads.payload.flatpak.initialization import (
    CalculateFlatpaksSizeTask,
)
from pyanaconda.modules.payloads.payload.flatpak.installation import (
    CleanUpDownloadLocationTask,
    DownloadFlatpaksTask,
    InstallFlatpaksTask,
    PrepareDownloadLocationTask,
)
from pyanaconda.modules.payloads.payload.payload_base import (
    SetUpSourcesTask,
    TearDownSourcesTask,
)
from pyanaconda.modules.payloads.source.factory import SourceFactory
from tests.unit_tests.pyanaconda_tests import (
    check_dbus_property,
    check_instances,
    check_task_creation,
    patch_dbus_publish_object,
)
from tests.unit_tests.pyanaconda_tests.modules.payloads.payload.module_payload_shared import (
    PayloadSharedTest,
)


class FlatpakInterfaceTestCase(unittest.TestCase):
    """Test the DBus interface of the Flatpak module."""

    def setUp(self):
        self.module = FlatpakModule()
        self.interface = FlatpakInterface(self.module)
        self.shared_tests = PayloadSharedTest(
            payload=self.module,
            payload_intf=self.interface
        )

    def test_type(self):
        """Test the Type property."""
        assert self.interface.Type == PAYLOAD_TYPE_FLATPAK

    def test_default_source_type(self):
        """Test the DefaultSourceType property."""
        assert self.interface.DefaultSourceType == ""

    def test_supported_sources(self):
        """Test Flatpak supported sources API."""
        assert self.interface.SupportedSourceTypes == []

    @patch.object(FlatpakModule, "supported_source_types", [SourceType.URL])
    @patch_dbus_publish_object
    def test_set_source(self, publisher):
        """Test if set source API Flatpak payload."""
        sources = [self.shared_tests.prepare_source(SourceType.URL)]
        repo = RepoConfigurationData()
        repo.url = "http://example.org"
        sources[0].set_configuration(repo)

        # TODO: this API is disabled on purpose, the behavior is currently wrong
        # sources stored in the payload are not really stored anywhere just passed
        # to flatpak_manager
        self.shared_tests.set_sources(sources)
        assert self.interface.Sources == []

    @patch_dbus_publish_object
    def test_set_up_sources_with_task(self, publisher):
        """Test Flatpak SetUpSourcesWithTask."""
        source = SourceFactory.create_source(SourceType.CDROM)
        self.module.add_source(source)

        task_path = self.interface.SetUpSourcesWithTask()
        obj = check_task_creation(task_path, publisher, SetUpSourcesTask)
        assert obj.implementation._sources == []

    @patch_dbus_publish_object
    def test_tear_down_sources_with_task(self, publisher):
        """Test TearDownSourcesWithTask."""
        s1 = SourceFactory.create_source(SourceType.CDROM)
        self.module.add_source(s1)

        task_path = self.interface.TearDownSourcesWithTask()
        obj = check_task_creation(task_path, publisher, TearDownSourcesTask)
        assert obj.implementation._sources == []

    @patch_dbus_publish_object
    def test_calculate_size_with_task(self, publisher):
        """Test CalculateSizeWithTask API."""
        task_path = self.interface.CalculateSizeWithTask()

        check_task_creation(task_path, publisher, CalculateFlatpaksSizeTask)

    def _check_dbus_property(self, *args, **kwargs):
        check_dbus_property(
            PAYLOAD_FLATPAK,
            self.interface,
            *args, **kwargs
        )


class FlatpakModuleTestCase(unittest.TestCase):
    """Test the Flatpak module."""

    def setUp(self):
        """Set up the test."""
        self.module = FlatpakModule()

    def test_is_network_required(self):
        """Test the Flatpak is_network_required function."""
        assert self.module.is_network_required() is False

    def test_set_sources(self):
        """Test set_sources method."""
        # FIXME: This method is hacked right now. As it will set sources only to Flatpak manager
        # and not the module.
        flatpak_manager = Mock()
        self.module._flatpak_manager = flatpak_manager
        s1 = SourceFactory.create_source(SourceType.URL)

        self.module.set_sources([s1])

        flatpak_manager.set_sources.assert_called_once_with([s1])

    def test_flatpak_refs(self):
        flatpak_manager = Mock()
        self.module._flatpak_manager = flatpak_manager

        refs = ["org.example.App",
                "org.example.App2"]

        self.module.set_flatpak_refs(refs)

        flatpak_manager.set_flatpak_refs.assert_called_once_with(refs)

    @patch("pyanaconda.modules.payloads.payload.flatpak.flatpak.calculate_required_space")
    def test_calculate_required_space(self, space_getter):
        """Test the Flatpak calculate_required_space method."""
        space_getter.return_value = Size("1 MiB")
        assert self.module.calculate_required_space() == 1048576

    def test_get_kernel_version_list(self):
        """Test the Flatpak get_kernel_version_list method."""
        with pytest.raises(UnavailableValueError):
            self.module.get_kernel_version_list()

    def test_install_with_tasks(self):
        """Test the Flatpak install_with_tasks method."""
        tasks = self.module.install_with_tasks()
        check_instances(tasks, [
            PrepareDownloadLocationTask,
            DownloadFlatpaksTask,
            InstallFlatpaksTask,
            CleanUpDownloadLocationTask,
        ])

    def test_post_install_with_tasks(self):
        """Test the Flatpak post_install_with_tasks method."""
        tasks = self.module.post_install_with_tasks()
        check_instances(tasks, [])
