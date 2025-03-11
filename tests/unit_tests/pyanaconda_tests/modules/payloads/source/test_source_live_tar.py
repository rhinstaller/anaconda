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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import os.path
import tarfile
import tempfile
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from dasbus.typing import Bool, Str, get_variant

from pyanaconda.core.constants import SOURCE_TYPE_LIVE_TAR
from pyanaconda.core.path import join_paths, make_directories, touch
from pyanaconda.modules.common.constants.interfaces import PAYLOAD_SOURCE_LIVE_IMAGE
from pyanaconda.modules.common.structures.live_image import LiveImageConfigurationData
from pyanaconda.modules.payloads.constants import SourceType
from pyanaconda.modules.payloads.source.live_tar.installation import InstallLiveTarTask
from pyanaconda.modules.payloads.source.live_tar.live_tar import LiveTarSourceModule
from tests.unit_tests.pyanaconda_tests import check_dbus_property


class LiveTarSourceInterfaceTestCase(unittest.TestCase):
    """Test the DBus interface of the live tar source."""

    def setUp(self):
        self.module = LiveTarSourceModule()
        self.interface = self.module.for_publication()

    def _check_dbus_property(self, *args, **kwargs):
        check_dbus_property(
            PAYLOAD_SOURCE_LIVE_IMAGE,
            self.interface,
            *args, **kwargs
        )

    def test_type(self):
        """Test the Type property."""
        assert self.interface.Type == SOURCE_TYPE_LIVE_TAR

    def test_description(self):
        """Test the Description property."""
        assert self.interface.Description == "Live tarball"

    def test_configuration(self):
        """Test the configuration property."""
        data = {
            "url": get_variant(Str, "http://my/image.tar.xz"),
            "proxy": get_variant(Str, "http://user:pass@example.com/proxy"),
            "checksum": get_variant(Str, "1234567890"),
            "ssl-verification-enabled": get_variant(Bool, False)
        }

        self._check_dbus_property(
            "Configuration",
            data
        )


class LiveTarSourceTestCase(unittest.TestCase):
    """Test the live tar source module."""

    def setUp(self):
        self.module = LiveTarSourceModule()

    def test_type(self):
        """Test the type property."""
        assert self.module.type == SourceType.LIVE_TAR

    def test_repr(self):
        """Test the string representation."""
        self.module.configuration.url = "file://my/path.tar.xz"
        assert repr(self.module) == str(
            "Source("
            "type='LIVE_TAR', "
            "url='file://my/path.tar.xz'"
            ")"
        )


class LiveTarInstallationTestCase(unittest.TestCase):
    """Test the live tar installation."""

    def setUp(self):
        """Set up the test."""
        self.data = LiveImageConfigurationData()
        self.directory = None

    @property
    def sysroot(self):
        """The sysroot directory."""
        return join_paths(self.directory, "sysroot")

    @property
    def tarball(self):
        """The tarball path."""
        return join_paths(self.directory, "test.tar")

    @contextmanager
    def _create_directory(self):
        """Create a temporary directory."""
        with tempfile.TemporaryDirectory() as d:
            self.directory = d
            yield
            self.directory = None

    def _create_tar(self, files):
        """Create a new tarball."""
        # Create the content.
        for path in files:
            file_path = join_paths(self.directory, path)
            make_directories(os.path.dirname(file_path))
            touch(file_path)

        # Create a local tarball.
        with tarfile.open(self.tarball, "w") as tar:
            for path in files:
                tar.add(join_paths(self.directory, path), path)

            tar.list()

        # Set up the configuration data.
        self.data.url = "file://" + self.tarball

    def _run_task(self):
        """Run the task."""
        os.makedirs(self.sysroot)

        task = InstallLiveTarTask(
            sysroot=self.sysroot,
            configuration=self.data
        )

        with patch('pyanaconda.core.dbus.DBus.get_proxy'):
            return task.run()

    def _check_content(self, files):
        """Check the sysroot content."""
        for path in files:
            file_path = join_paths(self.sysroot, path)
            assert os.path.exists(file_path)

    def test_install_files(self):
        """Install a tarball with files."""
        files = ["f1", "f2", "f3"]

        with self._create_directory():
            self._create_tar(files)
            result = self._run_task()
            self._check_content(files)

        assert result == []

    def test_install_kernels(self):
        """Install a tarball with kernels."""
        files = [
            "/boot/vmlinuz-0-rescue-dbe69c1b88f94a67b689e3f44b0550c8",
            "/boot/vmlinuz-5.8.15-201.fc32.x86_64",
            "/boot/vmlinuz-5.8.16-200.fc32.x86_64",
            "/boot/vmlinuz-5.8.18-200.fc32.x86_64",
        ]

        with self._create_directory():
            self._create_tar(files)
            result = self._run_task()
            self._check_content(files)

        assert result == [
            '5.8.15-201.fc32.x86_64',
            '5.8.16-200.fc32.x86_64',
            '5.8.18-200.fc32.x86_64',
        ]
