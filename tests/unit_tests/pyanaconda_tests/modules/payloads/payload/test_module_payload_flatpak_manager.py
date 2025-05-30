#
# Copyright (C) 2025  Red Hat, Inc.
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
from unittest.mock import Mock, call, patch

import gi
import pytest

from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.glib import GError
from pyanaconda.modules.common.errors.installation import PayloadInstallationError
from pyanaconda.modules.common.errors.payload import SourceSetupError
from pyanaconda.modules.common.structures.payload import RepoConfigurationData
from pyanaconda.modules.payloads.payload.flatpak.flatpak_manager import (
    FlatpakManager,
)
from pyanaconda.modules.payloads.payload.flatpak.source import (
    FlatpakRegistrySource,
    FlatpakStaticSource,
)
from pyanaconda.modules.payloads.source.cdn.cdn import CDNSourceModule
from pyanaconda.modules.payloads.source.closest_mirror.closest_mirror import (
    ClosestMirrorSourceModule,
)
from pyanaconda.modules.payloads.source.live_os.live_os import LiveOSSourceModule
from pyanaconda.modules.payloads.source.url.url import URLSourceModule

gi.require_version("Flatpak", "1.0")
gi.require_version("Gio", "2.0")

from gi.repository.Flatpak import TransactionOperationType

REMOTE_NAME = "Anaconda"
REMOTE_PATH = "file:///flatpak/repo"


class FlatpakManagerTestCase(unittest.TestCase):
    """Test FlatpakManager of the Flatpak module."""

    def test_default_values(self):
        """Test FlatpakManager default values."""
        fm = FlatpakManager()
        assert fm.skip_installation is True
        assert fm.flatpak_refs == []
        assert isinstance(fm.get_source(), FlatpakRegistrySource)
        assert fm.download_size == 0
        assert fm.install_size == 0
        assert fm.download_location is None

    def test_set_empty_sources(self):
        """Test FlatpakManager the set_sources method with empty sources."""
        fm = FlatpakManager()
        fm.set_sources([])
        assert isinstance(fm.get_source(), FlatpakRegistrySource)

    def test_set_sources(self):
        """Test FlatpakManager the set_sources method."""
        repo = RepoConfigurationData()
        repo.url = "http://example.org"
        source = URLSourceModule()
        source.set_configuration(repo)

        fm = FlatpakManager()
        fm.set_sources([source])
        fp_source = fm.get_source()

        assert isinstance(fp_source, FlatpakStaticSource)
        assert fp_source.repository_config == source.repository

        # another assignment of the same source should not change the source
        fm.set_sources([source])
        fp_source2 = fm.get_source()

        assert fp_source is fp_source2

    def test_set_multiple_sources(self):
        """Test FlatpakManager the set_sources method with multiple sources."""
        repo = RepoConfigurationData()
        repo.url = "http://example.org"
        source = URLSourceModule()
        source.set_configuration(repo)

        repo1 = RepoConfigurationData()
        repo1.url = "http://example2.org"
        source1 = URLSourceModule()
        source1.set_configuration(repo)

        # only the first one should be taken as it is taken as main
        fm = FlatpakManager()
        fm.set_sources([source, source1])
        fp_source = fm.get_source()

        assert isinstance(fp_source, FlatpakStaticSource)
        assert fp_source.repository_config == source.repository

    def test_set_source_with_cdn(self):
        """Test FlatpakManager the set_sources method with CDN source."""
        source = CDNSourceModule()

        fm = FlatpakManager()
        fm.set_sources([source])
        fp_source = fm.get_source()

        assert isinstance(fp_source, FlatpakRegistrySource)
        # the URL should be set to configuration value
        assert fp_source._url == conf.payload.flatpak_remote[1]

    def test_set_source_with_closest_mirror(self):
        """Test FlatpakManager the set_sources method with ClosestMirror source."""
        source = ClosestMirrorSourceModule()

        fm = FlatpakManager()
        fm.set_sources([source])
        fp_source = fm.get_source()

        assert isinstance(fp_source, FlatpakRegistrySource)
        # the URL should be set to configuration value
        assert fp_source._url == conf.payload.flatpak_remote[1]


    def test_set_source_with_unsupported_source(self):
        """Test FlatpakManager the set_sources method with unsupported source."""
        source = LiveOSSourceModule()

        fm = FlatpakManager()
        fm.set_sources([source])
        assert isinstance(fm.get_source(), FlatpakRegistrySource)

    def test_set_flatpak_refs(self):
        """Test FlatpakManager the set_flatpak_refs method."""
        fm = FlatpakManager()
        refs = ["org.fedoraproject.Stable:app/org.example.App1/amd64/stable"]

        assert fm.skip_installation is True
        assert fm.flatpak_refs == []

        fm.set_flatpak_refs(refs)

        assert fm.skip_installation is False
        assert fm.flatpak_refs == refs

    def test_download_location(self):
        """Test FlatpakManager the download_location method."""
        fm = FlatpakManager()

        assert fm.download_location is None

        fm.set_download_location("/test/location")

        assert fm.download_location == "/test/location"

    @patch.object(FlatpakManager, "get_source")
    def test_calculate_size(self, get_source_mock):
        """Test FlatpakManager the calculate_size method."""
        source = Mock()
        source.calculate_size.return_value = (10, 20)
        get_source_mock.return_value = source

        # should be skipped when skip installation is True
        fm = FlatpakManager()
        fm.calculate_size()
        source.calculate_size.assert_not_called()

        # should be skipped when no refs are set
        fm._skip_installation = False
        fm.calculate_size()
        source.calculate_size.assert_not_called()

        # the calculate method of source should be called
        fm._skip_installation = False
        refs = ["org.fedoraproject.Stable:app/org.example.App1/amd64/stable"]
        fm.set_flatpak_refs(refs)
        fm.calculate_size()
        source.calculate_size.assert_called_once_with(refs)
        assert fm.download_size == 10
        assert fm.install_size == 20

        # set skip installation to True if no source is set
        fm._skip_installation = False
        refs = ["org.fedoraproject.Stable:app/org.example.App1/amd64/stable"]
        source.calculate_size.side_effect = SourceSetupError
        fm.set_flatpak_refs(refs)
        fm.calculate_size()
        assert fm.skip_installation is True

    @patch.object(FlatpakManager, "get_source")
    def test_download(self, get_source_mock):
        """Test FlatpakManager the download method."""
        source = Mock()
        source.download.return_value = "download_location"
        get_source_mock.return_value = source
        progress = Mock()

        fm = FlatpakManager()

        # skip when skip installation is True
        fm.download(progress)
        get_source_mock.assert_not_called()

        # skip when refs are not set
        fm._skip_installation = False
        fm.download(progress)
        get_source_mock.assert_not_called()

        # works
        fm._skip_installation = False
        refs = ["org.fedoraproject.Stable:app/org.example.App1/amd64/stable"]
        fm.set_flatpak_refs(refs)
        fm.set_download_location("test-location")
        fm.download(progress)
        source.download.assert_called_once_with(refs,
                                                "test-location",
                                                progress)

        # source is not ready
        fm._skip_installation = False
        refs = ["org.fedoraproject.Stable:app/org.example.App1/amd64/stable"]
        fm.set_flatpak_refs(refs)
        fm.set_download_location("test-location")
        source.download.side_effect = SourceSetupError
        fm.download(progress)
        assert fm.skip_installation is True

    @patch("pyanaconda.modules.payloads.payload.flatpak.flatpak_manager.Transaction")
    @patch("pyanaconda.modules.payloads.payload.flatpak.flatpak_manager.Installation")
    def test_install(self, installation_mock, transaction_mock):
        """Test FlatpakManager the install method."""
        progress = Mock()
        installation = Mock()
        transaction = Mock()
        installation_mock.new_system.return_value = installation
        transaction_mock.new_for_installation.return_value = transaction

        fm = FlatpakManager()

        # skip when skip installation is True
        fm.install(progress)
        installation_mock.new_system.assert_not_called()

        # skip when refs are not set
        fm._skip_installation = False
        fm.install(progress)
        installation_mock.new_system.assert_not_called()

        # Working prerequisites
        fm._skip_installation = False
        refs = ["org.fedoraproject.Stable:app/org.example.App1/amd64/stable"]
        fm.set_flatpak_refs(refs)

        # run installation
        fm.install(progress)
        installation_mock.new_system.assert_called_once_with(None)
        transaction_mock.new_for_installation.assert_called_once_with(installation)
        transaction.add_sync_preinstalled.assert_called_once()
        transaction.run.assert_called_once()
        transaction.run_dispose.assert_called_once()

    @patch("pyanaconda.modules.payloads.payload.flatpak.flatpak_manager.Transaction")
    @patch("pyanaconda.modules.payloads.payload.flatpak.flatpak_manager.Installation")
    def test_install_with_collection(self, installation_mock, transaction_mock):
        """Test FlatpakManager the install method with collection location."""
        progress = Mock()
        installation = Mock()
        transaction = Mock()
        installation_mock.new_system.return_value = installation
        transaction_mock.new_for_installation.return_value = transaction
        remote = Mock()
        remote.get_url.return_value = "https://example.org"
        installation.list_remotes.return_value = [remote]

        fm = FlatpakManager()

        # Working prerequisites
        fm._skip_installation = False
        refs = ["org.fedoraproject.Stable:app/org.example.App1/amd64/stable"]
        fm.set_flatpak_refs(refs)

        # set collection
        fm._collection_location = "/example/location"

        # run installation
        fm.install(progress)
        installation_mock.new_system.assert_called_once_with(None)
        transaction_mock.new_for_installation.assert_called_once_with(installation)
        transaction.add_sideload_image_collection("/example/location")
        transaction.add_sync_preinstalled.assert_called_once()
        transaction.run.assert_called_once()
        transaction.run_dispose.assert_called_once()
        installation.modify_remote.assert_not_called()
        remote.set_url.assert_not_called()

    @patch("pyanaconda.modules.payloads.payload.flatpak.flatpak_manager.Transaction")
    @patch("pyanaconda.modules.payloads.payload.flatpak.flatpak_manager.Installation")
    def test_install_with_collection_local_remote(self, installation_mock, transaction_mock):
        """Test FlatpakManager the install method with workaround for local remote."""
        progress = Mock()
        installation = Mock()
        transaction = Mock()
        installation_mock.new_system.return_value = installation
        transaction_mock.new_for_installation.return_value = transaction
        remote = Mock()
        remote1 = Mock()
        remote.get_url.return_value = "oci+https://example.org"
        remote.get_name.return_value = "remote"
        remote1.get_url.return_value = "https://example.org"
        remote1.get_name.return_value = "remote1"
        installation.list_remotes.return_value = [remote, remote1]

        fm = FlatpakManager()

        # Working prerequisites
        fm._skip_installation = False
        refs = ["org.fedoraproject.Stable:app/org.example.App1/amd64/stable"]
        fm.set_flatpak_refs(refs)

        # set collection
        fm._collection_location = "/example/location"

        # run installation
        fm.install(progress)
        installation_mock.new_system.assert_called_once_with(None)
        transaction_mock.new_for_installation.assert_called_once_with(installation)
        transaction.add_sideload_image_collection("/example/location")
        transaction.add_sync_preinstalled.assert_called_once()
        transaction.run.assert_called_once()
        transaction.run_dispose.assert_called_once()
        # change the URL because of workaround to avoid blocking the installation on
        # an inaccessible mirror; this mirror is returned after the installation so
        # it could be used for updates
        remote.set_url.assert_has_calls(
            [call("oci+https://no-download.invalid"), call("oci+https://example.org")]
        )
        remote1.set_url.assert_not_called()
        installation.modify_remote.assert_called()

    @patch("pyanaconda.modules.payloads.payload.flatpak.flatpak_manager.Transaction")
    @patch("pyanaconda.modules.payloads.payload.flatpak.flatpak_manager.Installation")
    def test_install_with_error(self, installation_mock, transaction_mock):
        """Test FlatpakManager the install method with raised error."""
        progress = Mock()
        installation = Mock()
        transaction = Mock()
        installation_mock.new_system.return_value = installation
        transaction_mock.new_for_installation.return_value = transaction

        fm = FlatpakManager()

        # Working prerequisites
        fm._skip_installation = False
        refs = ["org.fedoraproject.Stable:app/org.example.App1/amd64/stable"]
        fm.set_flatpak_refs(refs)

        # raise error on transaction run
        transaction.run.side_effect = GError("Test error")

        # run installation
        with pytest.raises(PayloadInstallationError):
            fm.install(progress)
            transaction.run_dispose.assert_called_once()

    def _create_transaction_operation(self):
        operation = Mock()
        operation.get_ref.return_value = "org.fedoraproject.Stable:app/org.example.App1/amd64/stable"
        operation.get_operation_type.return_value = TransactionOperationType.INSTALL
        return operation

    def test_callbacks(self):
        """Test FlatpakManager the install method callbacks."""
        progress = Mock()
        operation = self._create_transaction_operation()

        fm = FlatpakManager()
        fm._progress = progress

        fm._operation_started_callback(transaction=Mock(),
                                       operation=operation,
                                       progress=progress)

        progress.report_progress.assert_called_once_with(
            "Installing org.fedoraproject.Stable:app/org.example.App1/amd64/stable"
        )

        fm._operation_stopped_callback(transaction=Mock(),
                                       operation=operation,
                                       _commit=Mock(),
                                       result=Mock())


        error_mock = Mock()
        error_mock.message = "Some error"
        fm._operation_error_callback(transaction=Mock(),
                                     operation=operation,
                                     error=error_mock,
                                     details=Mock)
