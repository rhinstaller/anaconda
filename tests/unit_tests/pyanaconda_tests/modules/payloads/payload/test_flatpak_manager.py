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

import os
import unittest
from tempfile import TemporaryDirectory
from unittest.mock import Mock, call, patch

import gi

from pyanaconda.modules.payloads.payload.rpm_ostree.flatpak_manager import (
    FlatpakManager,
)

gi.require_version("Flatpak", "1.0")
from gi.repository.Flatpak import RefKind


class FlatpakTest(unittest.TestCase):

    def setUp(self):
        self._remote = Mock()
        self._installation = Mock()
        self._transaction = Mock()

    def _setup_flatpak_objects(self, remote_cls, installation_cls, transaction_cls):
        remote_cls.new.return_value = self._remote
        installation_cls.new_for_path.return_value = self._installation
        transaction_cls.new_for_installation.return_value = self._transaction

        self._transaction.get_installation.return_value = self._installation

    def test_is_available(self):
        """Test check for flatpak availability of the system sources."""
        assert not FlatpakManager.is_source_available()

        with TemporaryDirectory() as temp:
            FlatpakManager.LOCAL_REMOTE_PATH = "file://" + temp

            assert FlatpakManager.is_source_available()

    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.flatpak_manager.Transaction")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.flatpak_manager.Installation")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.flatpak_manager.Remote")
    def test_initialize_with_path(self, remote_cls, installation_cls, transaction_cls):
        """Test flatpak initialize with path."""
        self._setup_flatpak_objects(remote_cls, installation_cls, transaction_cls)

        flatpak = FlatpakManager("/mock/system/root/path")
        flatpak.initialize_with_path("/test/path/installation")

        remote_cls.new.assert_called_once()
        installation_cls.new_for_path.assert_called_once()
        transaction_cls.new_for_installation.assert_called_once_with(self._installation)

        expected_remote_calls = [call.set_gpg_verify(False),
                                 call.set_url(flatpak.LOCAL_REMOTE_PATH)]
        assert self._remote.method_calls == expected_remote_calls

        expected_remote_calls = [call.add_remote(self._remote, False, None)]
        assert self._installation.method_calls == expected_remote_calls

    def test_cleanup_call_without_initialize(self):
        """Test the cleanup call without initialize."""
        flatpak = FlatpakManager("/tmp/flatpak-test")

        flatpak.cleanup()

    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.flatpak_manager.shutil.rmtree")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.flatpak_manager.Transaction")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.flatpak_manager.Installation")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.flatpak_manager.Remote")
    def test_cleanup_call_no_repo(self, remote_cls, installation_cls, transaction_cls, rmtree):
        """Test the cleanup call with no repository created."""
        flatpak = FlatpakManager("any path")

        self._setup_flatpak_objects(remote_cls, installation_cls, transaction_cls)

        file_mock_path = Mock()
        file_mock_path.get_path.return_value = "/install/test/path"
        self._installation.get_path.return_value = file_mock_path

        flatpak.initialize_with_path("/install/test/path")
        flatpak.cleanup()

        rmtree.assert_not_called()

    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.flatpak_manager.shutil.rmtree")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.flatpak_manager.Transaction")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.flatpak_manager.Installation")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.flatpak_manager.Remote")
    def test_cleanup_call_mock_repo(self, remote_cls, installation_cls, transaction_cls, rmtree):
        """Test the cleanup call with mocked repository."""
        flatpak = FlatpakManager("any path")

        self._setup_flatpak_objects(remote_cls, installation_cls, transaction_cls)

        with TemporaryDirectory() as temp:
            install_path = os.path.join(temp, "install/test/path")
            file_mock_path = Mock()
            file_mock_path.get_path.return_value = install_path
            self._installation.get_path.return_value = file_mock_path

            os.makedirs(install_path)

            flatpak.initialize_with_path(install_path)
            flatpak.cleanup()

            rmtree.assert_called_once_with(install_path)

    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.flatpak_manager.Transaction")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.flatpak_manager.Installation")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.flatpak_manager.Remote")
    def test_get_required_space(self, remote_cls, installation_cls, transaction_cls):
        """Test flatpak required space method."""
        flatpak = FlatpakManager("any path")

        self._setup_flatpak_objects(remote_cls, installation_cls, transaction_cls)

        flatpak.initialize_with_system_path()

        self._installation.list_remote_refs_sync.return_value = [
            RefMock(installed_size=2000),
            RefMock(installed_size=3000),
            RefMock(installed_size=100)
        ]

        installation_size = flatpak.get_required_size()

        assert installation_size == 5100

    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.flatpak_manager.Transaction")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.flatpak_manager.Installation")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.flatpak_manager.Remote")
    def test_get_empty_refs_required_space(self, remote_cls, installation_cls, transaction_cls):
        """Test flatpak required space method with no refs."""
        flatpak = FlatpakManager("any path")

        self._setup_flatpak_objects(remote_cls, installation_cls, transaction_cls)

        flatpak.initialize_with_system_path()

        self._installation.list_remote_refs_sync.return_value = []

        installation_size = flatpak.get_required_size()

        assert installation_size == 0

    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.flatpak_manager.Transaction")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.flatpak_manager.Installation")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.flatpak_manager.Remote")
    def test_install(self, remote_cls, installation_cls, transaction_cls):
        """Test flatpak installation is working."""
        flatpak = FlatpakManager("remote/path")

        self._setup_flatpak_objects(remote_cls, installation_cls, transaction_cls)

        flatpak.initialize_with_system_path()

        mock_ref_list = [
            RefMock(name="org.space.coolapp", kind=RefKind.APP, arch="x86_64", branch="stable"),
            RefMock(name="com.prop.notcoolapp", kind=RefKind.APP, arch="i386", branch="f36"),
            RefMock(name="org.space.coolruntime", kind=RefKind.RUNTIME, arch="x86_64",
                    branch="stable"),
            RefMock(name="com.prop.notcoolruntime", kind=RefKind.RUNTIME, arch="i386",
                    branch="f36")
        ]

        self._installation.list_remote_refs_sync.return_value = mock_ref_list

        flatpak.install_all()

        expected_calls = [call.connect("new_operation", flatpak._operation_started_callback),
                          call.connect("operation_done", flatpak._operation_stopped_callback),
                          call.connect("operation_error", flatpak._operation_error_callback),
                          call.add_install(FlatpakManager.LOCAL_REMOTE_NAME,
                                           mock_ref_list[0].format_ref(),
                                           None),
                          call.add_install(FlatpakManager.LOCAL_REMOTE_NAME,
                                           mock_ref_list[1].format_ref(),
                                           None),
                          call.add_install(FlatpakManager.LOCAL_REMOTE_NAME,
                                           mock_ref_list[2].format_ref(),
                                           None),
                          call.add_install(FlatpakManager.LOCAL_REMOTE_NAME,
                                           mock_ref_list[3].format_ref(),
                                           None),
                          call.run()]

        assert self._transaction.mock_calls == expected_calls

    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.flatpak_manager.Transaction")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.flatpak_manager.Installation")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.flatpak_manager.Remote")
    def test_add_remote(self, remote_cls, installation_cls, transaction_cls):
        """Test flatpak add new remote."""
        flatpak = FlatpakManager("remote/path")

        self._setup_flatpak_objects(remote_cls, installation_cls, transaction_cls)

        flatpak.initialize_with_system_path()
        flatpak.add_remote("hive", "url://zerglings/home")

        remote_cls.new.assert_called_with("hive")
        self._remote.set_gpg_verify.assert_called_with(True)
        self._remote.set_url("url://zerglings/home")
        assert remote_cls.new.call_count == 2
        assert self._installation.add_remote.call_count == 2

    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.flatpak_manager.Transaction")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.flatpak_manager.Installation")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.flatpak_manager.Remote")
    def test_remove_remote(self, remote_cls, installation_cls, transaction_cls):
        """Test flatpak remove a remote."""
        flatpak = FlatpakManager("remote/path")

        self._setup_flatpak_objects(remote_cls, installation_cls, transaction_cls)

        mock_remote1 = Mock()
        mock_remote2 = Mock()
        mock_remote1.get_name.return_value = "nest"
        mock_remote2.get_name.return_value = "hive"

        self._installation.list_remotes.return_value = [mock_remote1, mock_remote2]

        flatpak.initialize_with_system_path()
        flatpak.remove_remote("hive")

        self._installation.remove_remote.assert_called_once_with("hive", None)

    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.flatpak_manager.Variant")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.flatpak_manager.VariantType")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.flatpak_manager.open")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.flatpak_manager.Transaction")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.flatpak_manager.Installation")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.flatpak_manager.Remote")
    def test_replace_remote(self, remote_cls, installation_cls, transaction_cls,
                            open_mock, variant_type, variant):
        """Test flatpak replace remote for installed refs call."""
        flatpak = FlatpakManager("/system/test-root")

        self._setup_flatpak_objects(remote_cls, installation_cls, transaction_cls)

        install_path = "/installation/path"

        install_path_mock = Mock()
        install_path_mock.get_path.return_value = install_path
        self._installation.get_path.return_value = install_path_mock

        ref_mock_list = [
            RefMock(name="org.space.coolapp", kind=RefKind.APP, arch="x86_64", branch="stable"),
            RefMock(name="org.space.coolruntime", kind=RefKind.RUNTIME, arch="x86_64",
                    branch="stable")
        ]

        self._installation.list_installed_refs.return_value = ref_mock_list

        flatpak.initialize_with_system_path()
        flatpak.replace_installed_refs_remote("cylon_officer")

        expected_refs = list(map(lambda x: x.format_ref(), ref_mock_list))

        open_calls = []

        for ref in expected_refs:
            ref_file_path = os.path.join(install_path, ref, "active/deploy")
            open_calls.append(call(ref_file_path, "rb"))
            open_calls.append(call(ref_file_path, "wb"))

        # test that every file is read and written
        assert open_mock.call_count == 2 * len(expected_refs)

        open_mock.has_calls(open_calls)


class RefMock(object):

    def __init__(self, name="org.app", kind=RefKind.APP, arch="x86_64", branch="stable",
                 installed_size=0):
        self._name = name
        self._kind = kind
        self._arch = arch
        self._branch = branch
        self._installed_size = installed_size

    def get_name(self):
        return self._name

    def get_kind(self):
        return self._kind

    def get_arch(self):
        return self._arch

    def get_branch(self):
        return self._branch

    def get_installed_size(self):
        return self._installed_size

    def format_ref(self):
        return "{}/{}/{}/{}".format("app" if self._kind is RefKind.APP else "runtime",
                                    self._name,
                                    self._arch,
                                    self._branch)
