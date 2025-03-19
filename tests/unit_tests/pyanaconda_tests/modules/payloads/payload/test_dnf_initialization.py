#
# Copyright (C) 2023  Red Hat, Inc.
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
import subprocess
import unittest
from tempfile import TemporaryDirectory
from unittest.mock import Mock

import pytest
from dasbus.structure import compare_data

from pyanaconda.core.constants import REPO_ORIGIN_SYSTEM, REPO_ORIGIN_USER, REPO_ORIGIN_TREEINFO
from pyanaconda.core.path import make_directories, join_paths
from pyanaconda.modules.common.errors.payload import SourceSetupError
from pyanaconda.modules.common.structures.packages import PackagesConfigurationData
from pyanaconda.modules.common.structures.payload import RepoConfigurationData
from pyanaconda.modules.payloads.constants import SourceType
from pyanaconda.modules.payloads.payload.dnf.dnf_manager import DNFManager
from pyanaconda.modules.payloads.payload.dnf.initialization import SetUpDNFSourcesResult, \
    SetUpDNFSourcesTask, TearDownDNFSourcesTask
from pyanaconda.modules.payloads.source.factory import SourceFactory
from tests.unit_tests.pyanaconda_tests.modules.payloads.payload.test_dnf_tree_info import \
    TREE_INFO_RHEL


class SetUpDNFSourcesTaskTestCase(unittest.TestCase):
    """Test the SetUpDNFSourcesTask task."""

    def _create_repository(self, *paths):
        """Create a repository at the specified path."""
        path = join_paths(*paths)
        make_directories(path)

        subprocess.run(["createrepo_c", path], check=True)

    def _create_treeinfo(self, treeinfo, *paths):
        """Create a treeinfo file at the specified path."""
        path = join_paths(*paths)
        make_directories(path)

        with open(join_paths(path, ".treeinfo"), "w") as f:
            f.write(treeinfo)

    def _run_task(self, source=None, repositories=None):
        """Run the SetUpDNFSourcesTask task."""
        task = SetUpDNFSourcesTask(
            configuration=PackagesConfigurationData(),
            sources=[source] if source else [],
            repositories=repositories or [],
        )

        result = task.run()
        assert isinstance(result, SetUpDNFSourcesResult)
        assert isinstance(result.dnf_manager, DNFManager)
        assert result.dnf_manager.repositories
        assert result.dnf_manager.enabled_repositories

        return result

    def test_no_sources(self):
        """Set up no sources."""
        with pytest.raises(SourceSetupError) as cm:
            self._run_task()

        assert str(cm.value) == "No sources to set up!"

    def test_closest_mirror(self):
        """Set up the closest mirror."""
        source = SourceFactory.create_source(
            SourceType.CLOSEST_MIRROR
        )
        result = self._run_task(source)
        assert result.repositories == []
        assert result.sources == []

        dnf_manager = result.dnf_manager
        # There is no base repository configured.
        assert "anaconda" not in dnf_manager.repositories

    def test_cdn_source(self):
        """Set up the CDN source."""
        source = SourceFactory.create_source(
            SourceType.CDN
        )
        # Don't call any set up tasks.
        source.set_up_with_tasks = Mock(return_value=[])

        result = self._run_task(source)
        assert result.repositories == []
        assert result.sources == []

        dnf_manager = result.dnf_manager
        # There is no base repository configured.
        assert "anaconda" not in dnf_manager.repositories

    def test_valid_source(self):
        """Set up a valid source."""
        with TemporaryDirectory() as path:
            source = SourceFactory.create_source(
                SourceType.URL
            )

            self._create_repository(path)

            configuration = RepoConfigurationData()
            configuration.url = "file://" + path
            source.set_configuration(configuration)

            result = self._run_task(source)
            assert result.repositories == []
            assert result.sources == []

            dnf_manager = result.dnf_manager
            # There is only the base repository configured.
            assert dnf_manager.enabled_repositories == ["anaconda"]

    def test_source_proxy(self):
        """Set up a valid source with a proxy."""
        with TemporaryDirectory() as path:
            source = SourceFactory.create_source(
                SourceType.URL
            )

            self._create_repository(path)

            configuration = RepoConfigurationData()
            configuration.url = "file://" + path
            configuration.proxy = "http://proxy"
            source.set_configuration(configuration)

            result = self._run_task(source)

            dnf_manager = result.dnf_manager
            # The DNF manager should use the proxy of the source.
            assert dnf_manager._base.conf.proxy == "http://proxy:3128"

    def test_invalid_source(self):
        """Set up an invalid source."""
        source = SourceFactory.create_source(
            SourceType.URL
        )

        with TemporaryDirectory() as path:
            configuration = RepoConfigurationData()
            configuration.url = "file://" + path
            source.set_configuration(configuration)

            with pytest.raises(SourceSetupError) as cm:
                self._run_task(source)

        msg = "Failed to add the 'anaconda' repository:"
        assert str(cm.value).startswith(msg)

    def test_valid_repository(self):
        """Set up a valid additional repository."""
        with TemporaryDirectory() as path:
            self._create_repository(path)

            source = SourceFactory.create_source(
                SourceType.CLOSEST_MIRROR
            )

            repository = RepoConfigurationData()
            repository.name = "test"
            repository.url = "file://" + path

            result = self._run_task(source, [repository])
            assert result.repositories == [repository]
            assert len(result.sources) == 1

            dnf_manager = result.dnf_manager
            # The additional repository is configured.
            assert "test" in dnf_manager.enabled_repositories

    def test_invalid_repository(self):
        """Set up an invalid additional repository."""
        with TemporaryDirectory() as path:
            source = SourceFactory.create_source(
                SourceType.CLOSEST_MIRROR
            )

            repository = RepoConfigurationData()
            repository.name = "test"
            repository.url = "file://" + path

            with pytest.raises(SourceSetupError) as cm:
                self._run_task(source, [repository])

            msg = "Failed to add the 'test' repository:"
            assert str(cm.value).startswith(msg)

    def test_system_repository(self):
        """Set up a system repository."""
        with TemporaryDirectory() as path:
            self._create_repository(path)

            source = SourceFactory.create_source(
                SourceType.CLOSEST_MIRROR
            )

            # Configure a test repository.
            r1 = RepoConfigurationData()
            r1.origin = REPO_ORIGIN_USER
            r1.name = "test"
            r1.url = "file://" + path
            r1.enabled = True

            # Disable a test repository.
            # This is a little hack for testing.
            r2 = RepoConfigurationData()
            r2.origin = REPO_ORIGIN_SYSTEM
            r2.name = "test"
            r2.enabled = False

            result = self._run_task(source, [r1, r2])
            assert result.repositories == [r1, r2]
            assert len(result.sources) == 1

            dnf_manager = result.dnf_manager
            # The additional repository is configured, but disabled.
            assert "test" in dnf_manager.repositories
            assert "test" not in dnf_manager.enabled_repositories

    def test_treeinfo_repositories(self):
        """Set up a source with valid treeinfo metadata."""
        with TemporaryDirectory() as path:
            self._create_treeinfo(TREE_INFO_RHEL, path, "unified")
            self._create_repository(path, "baseos")
            self._create_repository(path, "appstream")

            source = SourceFactory.create_source(
                SourceType.URL
            )

            configuration = RepoConfigurationData()
            configuration.url = "file://{}/unified".format(path)
            source.set_configuration(configuration)

            result = self._run_task(source)
            dnf_manager = result.dnf_manager

            # The treeinfo release version is used.
            assert dnf_manager._base.conf.releasever == "8.5"

            # The treeinfo repositories are configured.
            assert dnf_manager.enabled_repositories == [
                "anaconda", "AppStream"
            ]

            # The treeinfo base repository is configured.
            repo_object = dnf_manager._get_repository("anaconda")
            assert repo_object.baseurl == ["file://{}/baseos".format(path)]

            # Check the generated treeinfo repository.
            repository = RepoConfigurationData()
            repository.name = "AppStream"
            repository.origin = REPO_ORIGIN_TREEINFO
            repository.url = "file://{}/appstream".format(path)

            assert len(result.repositories) == 1
            assert compare_data(result.repositories[0], repository)

            # Check the generated source of the treeinfo repository.
            assert len(result.sources) == 1
            assert result.sources[0].type == SourceType.URL
            assert compare_data(result.sources[0].configuration, repository)


class TearDownDNFSourcesTaskTestCase(unittest.TestCase):
    """Test the TearDownDNFSourcesTask task."""

    def test_tear_down_dnf_sources(self):
        """Test tear down of the DNF sources."""
        dnf_manager = DNFManager()

        s1 = SourceFactory.create_source(SourceType.CDROM)
        s2 = SourceFactory.create_source(SourceType.URL)
        s3 = SourceFactory.create_source(SourceType.NFS)

        task = TearDownDNFSourcesTask(
            sources=[s1, s2, s3],
            dnf_manager=dnf_manager,
        )
        task.run()
