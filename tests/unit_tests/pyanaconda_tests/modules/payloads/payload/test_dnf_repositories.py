#
# Copyright (C) 2022  Red Hat, Inc.
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
import tempfile
import unittest
from unittest.mock import MagicMock, call, patch

import pytest
from dasbus.structure import compare_data

from pyanaconda.core.constants import REPO_ORIGIN_SYSTEM
from pyanaconda.core.path import join_paths, make_directories, touch
from pyanaconda.modules.common.errors.payload import (
    SourceSetupError,
    UnknownRepositoryError,
)
from pyanaconda.modules.common.structures.payload import RepoConfigurationData
from pyanaconda.modules.payloads.constants import SourceType
from pyanaconda.modules.payloads.payload.dnf.dnf_manager import DNFManager
from pyanaconda.modules.payloads.payload.dnf.repositories import (
    create_repository,
    disable_default_repositories,
    enable_existing_repository,
    enable_updates_repositories,
    generate_driver_disk_repositories,
    generate_source_from_repository,
)


class DNFDriverDiskRepositoriesTestCase(unittest.TestCase):
    """Test the generate_driver_disk_repositories function."""

    @patch("pyanaconda.modules.payloads.payload.dnf.repositories.conf")
    def test_no_repository(self, conf_mock):
        """Test with no driver disk repositories."""
        conf_mock.system.can_use_driver_disks = True
        with tempfile.TemporaryDirectory() as d:
            assert generate_driver_disk_repositories(d) == []

    @patch("pyanaconda.modules.payloads.payload.dnf.repositories.conf")
    def test_empty_repository(self, conf_mock):
        """Test with empty driver disk repositories."""
        conf_mock.system.can_use_driver_disks = True
        with tempfile.TemporaryDirectory() as d:
            make_directories(join_paths(d, "DD-1"))
            assert generate_driver_disk_repositories(d) == []

    @patch("pyanaconda.modules.payloads.payload.dnf.repositories.conf")
    def test_repository_without_metadata(self, conf_mock):
        """Test with one driver disk repository without metadata."""
        conf_mock.system.can_use_driver_disks = True
        with tempfile.TemporaryDirectory() as d:
            make_directories(join_paths(d, "DD-1"))
            touch(join_paths(d, "DD-1", "x.rpm"))
            assert not os.path.exists(join_paths(d, "DD-1", "repodata"))

            (r, *rs) = generate_driver_disk_repositories(d)

            assert rs == []
            assert r.name == "DD-1"
            assert r.url == "file://{}/DD-1".format(d)
            assert os.path.exists(join_paths(d, "DD-1", "repodata"))

    @patch("pyanaconda.modules.payloads.payload.dnf.repositories.conf")
    def test_repository_with_metadata(self, conf_mock):
        """Test with one driver disk repository."""
        conf_mock.system.can_use_driver_disks = True
        with tempfile.TemporaryDirectory() as d:
            make_directories(join_paths(d, "DD-1"))
            make_directories(join_paths(d, "DD-1", "repodata"))
            touch(join_paths(d, "DD-1", "x.rpm"))

            (r, *rs) = generate_driver_disk_repositories(d)

            assert rs == []
            assert r.name == "DD-1"
            assert r.url == "file://{}/DD-1".format(d)

    @patch("pyanaconda.modules.payloads.payload.dnf.repositories.conf")
    def test_repositories(self, conf_mock):
        """Test with multiple driver disk repositories."""
        conf_mock.system.can_use_driver_disks = True
        with tempfile.TemporaryDirectory() as d:
            make_directories(join_paths(d, "DD-1"))
            touch(join_paths(d, "DD-1", "x.rpm"))

            make_directories(join_paths(d, "DD-2"))
            touch(join_paths(d, "DD-2", "y.rpm"))

            make_directories(join_paths(d, "DD-3"))
            touch(join_paths(d, "DD-3", "z.rpm"))

            (r1, r2, r3, *rs) = generate_driver_disk_repositories(d)

            assert rs == []
            assert r1.name == "DD-1"
            assert r1.url == "file://{}/DD-1".format(d)

            assert r2.name == "DD-2"
            assert r2.url == "file://{}/DD-2".format(d)

            assert r3.name == "DD-3"
            assert r3.url == "file://{}/DD-3".format(d)

    @patch("pyanaconda.modules.payloads.payload.dnf.repositories.conf")
    def test_disabled(self, conf_mock):
        """Test when disabled with one driver disk repository.

        This is a copy of test_repository_with_metadata but with the code disabled.
        """
        conf_mock.system.can_use_driver_disks = False
        with tempfile.TemporaryDirectory() as d:
            make_directories(join_paths(d, "DD-1"))
            make_directories(join_paths(d, "DD-1", "repodata"))
            touch(join_paths(d, "DD-1", "x.rpm"))

            assert generate_driver_disk_repositories(d) == []


class DNFGenerateSourcesTestCase(unittest.TestCase):
    """Test the generate_source_from_repository function."""

    def test_system_repository(self):
        """Don't generate sources for system repositories."""
        repository = RepoConfigurationData()
        repository.name = "test"
        repository.origin = REPO_ORIGIN_SYSTEM

        with pytest.raises(ValueError) as cm:
            generate_source_from_repository(repository)

        assert str(cm.value) == "Unsupported origin of the 'test' repository: SYSTEM"

    def test_missing_url(self):
        """Don't generate sources for repositories without urls."""
        repository = RepoConfigurationData()
        repository.name = "test"

        with pytest.raises(SourceSetupError) as cm:
            generate_source_from_repository(repository)

        assert str(cm.value) == "The 'test' repository has no mirror, baseurl or metalink set."

    def test_unsupported_protocol(self):
        """Don't generate sources for repositories with invalid protocols."""
        repository = RepoConfigurationData()
        repository.name = "test"
        repository.url = "invalid://path"

        with pytest.raises(SourceSetupError) as cm:
            generate_source_from_repository(repository)

        assert str(cm.value) == "The 'test' repository uses an unsupported protocol."

    def test_nfs_repository(self):
        """Generate a source for an NFS repository."""
        repository = RepoConfigurationData()
        repository.name = "test"
        repository.url = "nfs:server:path"

        source = generate_source_from_repository(repository)
        assert source.type == SourceType.NFS
        assert compare_data(source.configuration, repository)

    def test_nfs_repository_substitutions(self):
        """Generate a source for an NFS repository with substitutions."""
        dnf_manager = DNFManager()
        dnf_manager.configure_substitution(release_version="12.3")

        repository = RepoConfigurationData()
        repository.name = "test"
        repository.url = "nfs:server:/path/product/$releasever/"

        expected = RepoConfigurationData()
        expected.name = "test"
        expected.url = "nfs:server:/path/product/12.3/"

        source = generate_source_from_repository(repository, dnf_manager.substitute)
        assert source.type == SourceType.NFS
        assert compare_data(source.configuration, expected)

    def test_hdd_repository(self):
        """Generate a source for an HDD repository."""
        repository = RepoConfigurationData()
        repository.name = "test"
        repository.url = "hd:device:path"

        source = generate_source_from_repository(repository)
        assert source.type == SourceType.HDD
        assert compare_data(source.configuration, repository)

    def test_ftp_repository(self):
        """Generate a source for a FTP repository."""
        repository = RepoConfigurationData()
        repository.name = "test"
        repository.url = "ftp://server"

        source = generate_source_from_repository(repository)
        assert source.type == SourceType.URL
        assert compare_data(source.configuration, repository)

    def test_http_repository(self):
        """Generate a source for a HTTP repository."""
        repository = RepoConfigurationData()
        repository.name = "test"
        repository.url = "http://server"

        source = generate_source_from_repository(repository)
        assert source.type == SourceType.URL
        assert compare_data(source.configuration, repository)

    def test_file_repository(self):
        """Generate a source for a local repository."""
        repository = RepoConfigurationData()
        repository.name = "test"
        repository.url = "file:///path"

        source = generate_source_from_repository(repository)
        assert source.type == SourceType.URL
        assert compare_data(source.configuration, repository)


class DNFRepositoriesUtilsTestCase(unittest.TestCase):
    """Test utilities for DNF repositories."""

    @patch("pyanaconda.modules.payloads.payload.dnf.repositories.conf")
    def test_enable_updates_repositories(self, mocked_conf):
        """Test the enable_updates_repositories function."""
        mocked_conf.payload.updates_repositories = [
            "updates",
            "updates-modular"
        ]

        dnf_manager = MagicMock(spec=DNFManager)
        dnf_manager.get_matching_repositories.return_value = [
            "r1", "r2", "r3"
        ]

        enable_updates_repositories(dnf_manager, True)
        assert dnf_manager.get_matching_repositories.mock_calls == [
            call("updates"),
            call("updates-modular"),
        ]
        assert dnf_manager.set_repository_enabled.mock_calls == [
            call("r1", True),
            call("r2", True),
            call("r3", True),
        ]

    @patch("pyanaconda.modules.payloads.payload.dnf.repositories.get_product_is_final_release",
           return_value=True)
    def test_disable_default_repositories(self, mock_isfinal):
        """Test the disable_default_repositories function."""
        dnf_manager = MagicMock(spec=DNFManager)
        dnf_manager.get_matching_repositories.return_value = [
            "r1", "r2", "r3"
        ]

        disable_default_repositories(dnf_manager)
        assert dnf_manager.get_matching_repositories.mock_calls == [
            call("*source*"),
            call("*debuginfo*"),
            call("updates-testing"),
            call("updates-testing-modular"),
            call("*rawhide*"),
        ]

    @patch("pyanaconda.modules.payloads.payload.dnf.repositories.get_product_is_final_release",
           return_value=False)
    def test_disable_default_repositories_rawhide(self, mock_isfinal):
        """Test the disable_default_repositories function for Rawhide."""
        dnf_manager = MagicMock(spec=DNFManager)
        dnf_manager.get_matching_repositories.return_value = [
            "r1", "r2", "r3"
        ]

        disable_default_repositories(dnf_manager)
        assert dnf_manager.get_matching_repositories.mock_calls == [
            call("*source*"),
            call("*debuginfo*"),
            call("updates-testing"),
            call("updates-testing-modular"),
        ]
        assert dnf_manager.set_repository_enabled.mock_calls == [
            call("r1", False),
            call("r2", False),
            call("r3", False),
        ]

    def test_create_repository(self):
        """Test the create_repository function."""
        dnf_manager = MagicMock(spec=DNFManager)

        repository = RepoConfigurationData()
        repository.name = "test"
        repository.url = "file:///path"

        create_repository(dnf_manager, repository)
        dnf_manager.add_repository.assert_called_once_with(repository)
        dnf_manager.load_repository.assert_called_once_with("test")

    def test_enable_existing_repository(self):
        """Test the enable_existing_repository function."""
        dnf_manager = MagicMock(spec=DNFManager)

        repository = RepoConfigurationData()
        repository.name = "test"
        repository.url = "file:///path"
        repository.enabled = True

        enable_existing_repository(dnf_manager, repository)
        dnf_manager.set_repository_enabled.assert_called_once_with("test", True)

    def test_disable_existing_repository(self):
        """Test the enable_existing_repository function with a disabled repository."""
        dnf_manager = MagicMock(spec=DNFManager)

        repository = RepoConfigurationData()
        repository.name = "test"
        repository.url = "file:///path"
        repository.enabled = False

        enable_existing_repository(dnf_manager, repository)
        dnf_manager.set_repository_enabled.assert_called_once_with("test", False)

    def test_enable_unknown_repository(self):
        """Test the enable_existing_repository function with an unknown repository."""
        dnf_manager = MagicMock(spec=DNFManager)
        dnf_manager.set_repository_enabled.side_effect = UnknownRepositoryError("Fake!")

        repository = RepoConfigurationData()
        repository.name = "test"
        repository.url = "file:///path"
        repository.enabled = True

        with pytest.raises(SourceSetupError) as cm:
            enable_existing_repository(dnf_manager, repository)

        msg = "The 'test' repository is not one of the pre-defined repositories."
        assert str(cm.value) == msg
