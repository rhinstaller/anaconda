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
import unittest
import os
import gi

from tempfile import TemporaryDirectory
from unittest.mock import patch, Mock, call

from pyanaconda.modules.payloads.payload.rpm_ostree.flatpak_manager import FlatpakManager

gi.require_version("Flatpak", "1.0")
from gi.repository.Flatpak import TransactionOperationType


class FlatpakTest(unittest.TestCase):
    """Test the Flatpak manager"""

    def setUp(self):
        self._remote = Mock()
        self._installation = Mock()
        self._transaction = Mock()

    def _setup_flatpak_objects(self, remote_cls, installation_cls, transaction_cls):
        """Set up the Flatpak objects."""
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

        assert self._remote.method_calls == [
            call.set_gpg_verify(False),
            call.set_url(flatpak.LOCAL_REMOTE_PATH)
        ]

        assert self._installation.method_calls == [
            call.add_remote(self._remote, False, None)
        ]

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

        assert flatpak.get_required_size() == 5100

    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.flatpak_manager.Transaction")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.flatpak_manager.Installation")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.flatpak_manager.Remote")
    def test_get_empty_refs_required_space(self, remote_cls, installation_cls, transaction_cls):
        """Test flatpak required space method with no refs."""
        flatpak = FlatpakManager("any path")
        self._setup_flatpak_objects(remote_cls, installation_cls, transaction_cls)

        flatpak.initialize_with_system_path()
        self._installation.list_remote_refs_sync.return_value = []

        assert flatpak.get_required_size() == 0

    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.flatpak_manager.Transaction")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.flatpak_manager.Installation")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.flatpak_manager.Remote")
    def test_install(self, remote_cls, installation_cls, transaction_cls):
        """Test flatpak installation is working."""
        progress = Mock()
        flatpak = FlatpakManager(
            sysroot="remote/path",
            callback=progress
        )

        self._setup_flatpak_objects(remote_cls, installation_cls, transaction_cls)
        flatpak.initialize_with_system_path()

        self._installation.list_remote_refs_sync.return_value = [
            RefMock("app/org.space.coolapp/x86_64/stable"),
            RefMock("app/com.prop.notcoolapp/i386/f36"),
            RefMock("runtime/org.space.coolruntime/x86_64/stable"),
            RefMock("runtime/com.prop.notcoolruntime/i386/f36"),
        ]

        flatpak.install_all()
        assert self._transaction.mock_calls == [
            call.connect(
                "new_operation",
                flatpak._operation_started_callback
            ),
            call.connect(
                "operation_done",
                flatpak._operation_stopped_callback
            ),
            call.connect(
                "operation_error",
                flatpak._operation_error_callback
            ),
            call.add_install(
                FlatpakManager.LOCAL_REMOTE_NAME,
                "app/org.space.coolapp/x86_64/stable",
                None
            ),
            call.add_install(
                FlatpakManager.LOCAL_REMOTE_NAME,
                "app/com.prop.notcoolapp/i386/f36",
                None
            ),
            call.add_install(
                FlatpakManager.LOCAL_REMOTE_NAME,
                "runtime/org.space.coolruntime/x86_64/stable",
                None
            ),
            call.add_install(
                FlatpakManager.LOCAL_REMOTE_NAME,
                "runtime/com.prop.notcoolruntime/i386/f36",
                None
            ),
            call.run()
        ]

        assert progress.mock_calls == []

    def test_operation_started_callback(self):
        """Test the callback for started operations."""
        progress = Mock()
        flatpak = FlatpakManager(
            sysroot="remote/path",
            callback=progress
        )

        with self.assertLogs(level="DEBUG") as cm:
            flatpak._operation_started_callback(
                transaction=Mock(),
                operation=OperationMock("app/org.test"),
                progress=Mock(),
            )

        progress.assert_called_once_with("Installing app/org.test")

        msg = "Flatpak operation: install of ref app/org.test state started"
        assert msg in "\n".join(cm.output)

    def test_disabled_progress_reporting(self):
        """Test a callback with disabled progress reporting."""
        flatpak = FlatpakManager(
            sysroot="remote/path"
        )

        flatpak._operation_started_callback(
            transaction=Mock(),
            operation=OperationMock(),
            progress=Mock(),
        )

    def test_operation_stopped_callback(self):
        """Test the callback for stopped operations."""
        progress = Mock()
        flatpak = FlatpakManager(
            sysroot="remote/path",
            callback=progress
        )

        with self.assertLogs(level="DEBUG") as cm:
            flatpak._operation_stopped_callback(
                transaction=Mock(),
                operation=OperationMock("app/org.test"),
                commit=Mock(),
                result=Mock(),
            )

        progress.assert_not_called()

        msg = "Flatpak operation: install of ref app/org.test state stopped"
        assert msg in "\n".join(cm.output)

    def test_operation_error_callback(self):
        """Test the callback for failed operations."""
        progress = Mock()
        flatpak = FlatpakManager(
            sysroot="remote/path",
            callback=progress
        )

        with self.assertLogs(level="DEBUG") as cm:
            flatpak._operation_error_callback(
                transaction=Mock(),
                operation=OperationMock("app/org.test"),
                error=Mock(message="Fake!"),
                details=Mock(),
            )

        progress.assert_not_called()

        msg = "Flatpak operation: install of ref app/org.test state failed"
        assert msg in "\n".join(cm.output)

        msg = "Flatpak operation has failed with a message: 'Fake!'"
        assert msg in "\n".join(cm.output)

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

        install_path_mock = Mock()
        install_path_mock.get_path.return_value = "/path"

        self._installation.get_path.return_value = install_path_mock
        self._installation.list_installed_refs.return_value = [
            RefMock("app/org.test/x86_64/stable"),
            RefMock("runtime/org.run/x86_64/stable"),
        ]

        flatpak.initialize_with_system_path()
        flatpak.replace_installed_refs_remote("cylon_officer")

        # test that every file is read and written
        open_mock.assert_has_calls([
            call("/path/app/org.test/x86_64/stable/active/deploy", "rb"),
            call("/path/app/org.test/x86_64/stable/active/deploy", "wb"),
            call("/path/runtime/org.run/x86_64/stable/active/deploy", "rb"),
            call("/path/runtime/org.run/x86_64/stable/active/deploy", "wb"),
        ], any_order=True)


class OperationMock(object):
    """Mock of the Flatpak.TransactionOperation class."""

    def __init__(self, ref="app/org.test/x86_64", op=TransactionOperationType.INSTALL):
        self._ref = ref
        self._op = op

    def get_ref(self):
        return self._ref

    def get_operation_type(self):
        return self._op


class RefMock(object):
    """Mock of the Flatpak.InstalledRef class."""

    def __init__(self, ref="app/org.test/x86_64", installed_size=0):
        self._ref = ref
        self._installed_size = installed_size

    def get_installed_size(self):
        return self._installed_size

    def format_ref(self):
        return self._ref
