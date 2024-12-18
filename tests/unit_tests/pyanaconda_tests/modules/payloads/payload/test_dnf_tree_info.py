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
import os.path
import tempfile
import unittest
from unittest.mock import Mock, patch

import pytest
from dasbus.structure import compare_data

from pyanaconda.core.constants import (
    NETWORK_CONNECTION_TIMEOUT,
    REPO_ORIGIN_TREEINFO,
    URL_TYPE_METALINK,
)
from pyanaconda.modules.common.structures.payload import RepoConfigurationData
from pyanaconda.modules.payloads.payload.dnf.repositories import (
    update_treeinfo_repositories,
)
from pyanaconda.modules.payloads.payload.dnf.tree_info import (
    InvalidTreeInfoError,
    LoadTreeInfoMetadataResult,
    LoadTreeInfoMetadataTask,
    NoTreeInfoError,
    TreeInfoMetadata,
    generate_treeinfo_repository,
)

TREE_INFO_FEDORA = """
[header]
type = productmd.treeinfo
version = 1.2

[release]
name = Fedora
short = Fedora
version = 34

[tree]
arch = x86_64
build_timestamp = 1619258095
platforms = x86_64,xen
variants = Everything

[variant-Everything]
id = Everything
name = Everything
packages = Packages
repository = .
type = variant
uid = Everything
"""

TREE_INFO_RHEL = """
[header]
type = productmd.treeinfo
version = 1.2

[release]
name = Red Hat Enterprise Linux
short = RHEL
version = 8.5

[tree]
arch = x86_64
build_timestamp = 1621578929
platforms = x86_64,xen
variants = BaseOS,AppStream

[variant-BaseOS]
id = BaseOS
name = BaseOS
packages = ../baseos/Packages
repository = ../baseos
type = variant
uid = BaseOS

[variant-AppStream]
id = AppStream
name = AppStream
packages = ../appstream/Packages
repository = ../appstream
type = variant
uid = AppStream
"""

TREE_INFO_CUSTOM = """
[header]
type = productmd.treeinfo
version = 1.2

[release]
name = Custom
short = Custom
version = 1.0

[tree]
arch = x86_64
build_timestamp = 1619258095
platforms = x86_64,xen
variants = MyVariant,MyOptional

[variant-MyVariant]
addons = MyVariant-MyAddon
id = MyVariant
name = MyVariant
packages = ./variant/Packages
repository = ./variant
type = variant
uid = MyVariant

[addon-MyVariant-MyAddon]
id = MyAddon
name = MyAddon
packages = ./addon/Packages
parent = MyVariant
repository = ./addon
type = addon
uid = MyVariant-MyAddon

[variant-MyOptional]
id = MyOptional
name = MyOptional
packages = ./optional/Packages
repository = ./optional
type = optional
uid = MyOptional
"""

TREE_INFO_INVALID = """
[header]
type = productmd.treeinfo
version = 1.2

[release]
name = Custom
short = Custom
"""


class TreeInfoMetadataTestCase(unittest.TestCase):
    """Test the abstraction of the treeinfo metadata."""

    def setUp(self):
        self.maxDiff = None
        self.metadata = TreeInfoMetadata()
        self.metadata.MAX_TREEINFO_DOWNLOAD_RETRIES = 2

    def _create_file(self, root_path, file_name, content):
        """Create a new file."""
        file_path = os.path.join(root_path, file_name)

        with open(file_path, "w") as f:
            f.write(content)

    def _create_directory(self, root_path, dir_name):
        """Create a new directory."""
        dir_path = os.path.join(root_path, dir_name)
        os.mkdir(dir_path)

    def _load_treeinfo(self, content):
        """Load the specified treeinfo."""
        with tempfile.TemporaryDirectory(dir="/tmp") as root_path:
            self._create_file(
                root_path=root_path,
                file_name=".treeinfo",
                content=content
            )

            self._create_directory(
                root_path=root_path,
                dir_name="repodata"
            )

            repo_data = RepoConfigurationData()
            repo_data.url = "file://" + root_path
            self.metadata.load_data(repo_data)

        return repo_data.url

    def test_invalid_tree_info(self):
        """Test an invalid treeinfo metadata."""
        with pytest.raises(InvalidTreeInfoError) as cm:
            self._load_treeinfo(TREE_INFO_INVALID)

        msg = "Invalid metadata: No option 'version' in section: 'release'"
        assert str(cm.value) == msg

        assert self.metadata.release_version == ""
        assert self.metadata.repositories == []
        assert self.metadata.get_base_repository() is None
        assert self.metadata.get_root_repository() is None

    def test_release_version(self):
        """Test the release_version property."""
        self._load_treeinfo(TREE_INFO_FEDORA)
        assert self.metadata.release_version == "34"

        self._load_treeinfo(TREE_INFO_RHEL)
        assert self.metadata.release_version == "8.5"

    def test_rhel_treeinfo(self):
        """Test the RHEL metadata."""
        self._load_treeinfo(TREE_INFO_RHEL)
        assert len(self.metadata.repositories) == 2

        repo_md = self.metadata.repositories[0]
        assert repo_md.name == "AppStream"
        assert repo_md.type == "variant"
        assert repo_md.enabled is True
        assert repo_md.relative_path == "../appstream"
        assert repo_md.url == "file:///tmp/appstream"

        repo_md = self.metadata.repositories[1]
        assert repo_md.name == "BaseOS"
        assert repo_md.type == "variant"
        assert repo_md.enabled is True
        assert repo_md.relative_path == "../baseos"
        assert repo_md.url == "file:///tmp/baseos"

        assert self.metadata.get_base_repository() is repo_md
        assert self.metadata.get_root_repository() is None

    def test_fedora_treeinfo(self):
        """Test the Fedora metadata."""
        root_url = self._load_treeinfo(TREE_INFO_FEDORA)
        assert len(self.metadata.repositories) == 1

        repo_md = self.metadata.repositories[0]
        assert repo_md.name == "Everything"
        assert repo_md.type == "variant"
        assert repo_md.enabled is True
        assert repo_md.relative_path == "."
        assert repo_md.url == root_url

        assert self.metadata.get_base_repository() is None
        assert self.metadata.get_root_repository() is repo_md

    @patch("pyanaconda.modules.payloads.payload.dnf.tree_info.conf")
    def test_custom_treeinfo(self, mock_conf):
        """Test the custom metadata."""
        mock_conf.payload.enabled_repositories_from_treeinfo = ["variant"]
        root_url = self._load_treeinfo(TREE_INFO_CUSTOM)

        # Anaconda ignores child variants (for example, addons).
        assert len(self.metadata.repositories) == 2

        repo_md = self.metadata.repositories[0]
        assert repo_md.name == "MyOptional"
        assert repo_md.type == "optional"
        assert repo_md.enabled is False
        assert repo_md.relative_path == "./optional"
        assert repo_md.url == root_url + "/optional"

        repo_md = self.metadata.repositories[1]
        assert repo_md.name == "MyVariant"
        assert repo_md.type == "variant"
        assert repo_md.enabled is True
        assert repo_md.relative_path == "./variant"
        assert repo_md.url == root_url + "/variant"

        assert self.metadata.get_base_repository() is None
        assert self.metadata.get_root_repository() is None

    def test_verify_image_base_repo(self):
        """Test the verify_image_base_repo method."""
        # No repository.
        assert not self.metadata.verify_image_base_repo()

        with tempfile.TemporaryDirectory() as path:
            # No base or root repository.
            self._create_file(path, ".treeinfo", TREE_INFO_CUSTOM)
            self.metadata.load_file(path)
            assert not self.metadata.verify_image_base_repo()

        with tempfile.TemporaryDirectory() as path:
            # Invalid base repository.
            self._create_file(path, ".treeinfo", TREE_INFO_RHEL)
            self.metadata.load_file(path)
            assert not self.metadata.verify_image_base_repo()

        with tempfile.TemporaryDirectory() as path:
            # Invalid root repository.
            self._create_file(path, ".treeinfo", TREE_INFO_FEDORA)
            self.metadata.load_file(path)
            assert not self.metadata.verify_image_base_repo()

        with tempfile.TemporaryDirectory() as path:
            # Valid base or root repository.
            self._create_file(path, ".treeinfo", TREE_INFO_FEDORA)
            self._create_directory(path, "repodata")
            self.metadata.load_file(path)
            assert self.metadata.verify_image_base_repo()

    def test_load_file(self):
        """Test the load_file method."""
        # No metadata file.
        with tempfile.TemporaryDirectory() as path:
            with pytest.raises(NoTreeInfoError) as cm:
                self.metadata.load_file(path)

            assert str(cm.value) == "No treeinfo metadata found."

        # Load the .treeinfo file.
        with tempfile.TemporaryDirectory() as path:
            self._create_file(path, ".treeinfo", TREE_INFO_FEDORA)
            self.metadata.load_file(path)

        # Load the treeinfo file.
        with tempfile.TemporaryDirectory() as path:
            self._create_file(path, "treeinfo", TREE_INFO_FEDORA)
            self.metadata.load_file(path)

    def test_load_data_unsupported_url(self):
        """Test the load_data method with an unsupported URL."""
        data = RepoConfigurationData()
        data.type = URL_TYPE_METALINK

        with pytest.raises(NoTreeInfoError) as cm:
            self.metadata.load_data(data)

        assert str(cm.value) == "Unsupported type of URL (METALINK)."

    def test_load_data_missing_url(self):
        """Test the load_data method with a missing URL."""
        data = RepoConfigurationData()
        data.url = ""

        with pytest.raises(NoTreeInfoError) as cm:
            self.metadata.load_data(data)

        assert str(cm.value) == "No URL specified."

    def test_load_data_failed_download(self):
        """Test the load_data method with no metadata."""
        with tempfile.TemporaryDirectory() as path:
            data = RepoConfigurationData()
            data.url = "invalid://" + path

            with pytest.raises(NoTreeInfoError) as cm:
                self.metadata.load_data(data)

            assert str(cm.value) == "Couldn't download treeinfo metadata."

    def test_load_data_no_metadata(self):
        """Test the load_data method with no metadata."""
        with tempfile.TemporaryDirectory() as path:
            data = RepoConfigurationData()
            data.url = "file://" + path

            with pytest.raises(NoTreeInfoError) as cm:
                self.metadata.load_data(data)

            assert str(cm.value) == "No treeinfo metadata found (404)."

    def test_load_data(self):
        """Test the load_data method."""
        # Load the .treeinfo file.
        with tempfile.TemporaryDirectory() as path:
            self._create_file(path, ".treeinfo", TREE_INFO_FEDORA)

            data = RepoConfigurationData()
            data.url = "file://" + path

            self.metadata.load_data(data)

        # Load the treeinfo file.
        with tempfile.TemporaryDirectory() as path:
            self._create_file(path, "treeinfo", TREE_INFO_FEDORA)

            data = RepoConfigurationData()
            data.url = "file://" + path

            self.metadata.load_data(data)

    @patch("requests.Session.get")
    def test_load_data_ssl(self, session_getter):
        """Test the load_data method with SSL configuration."""
        session_getter.return_value.__enter__.return_value = \
            Mock(status_code=200, text=TREE_INFO_FEDORA)

        data = RepoConfigurationData()
        data.url = "http://path"
        data.ssl_verification_enabled = True
        data.ssl_configuration.ca_cert_path = "file.cert"
        data.ssl_configuration.client_key_path = "client.key"
        data.ssl_configuration.client_cert_path = "client.cert"

        self.metadata.load_data(data)

        session_getter.assert_called_once_with(
            "http://path/.treeinfo",
            headers={"user-agent": "anaconda (anaconda)/bluesky"},
            proxies={},
            verify="file.cert",
            cert=("client.cert", "client.key"),
            timeout=NETWORK_CONNECTION_TIMEOUT
        )

    @patch("requests.Session.get")
    def test_load_data_proxy(self, session_getter):
        """Test the load_data method with proxy configuration."""
        session_getter.return_value.__enter__.return_value = \
            Mock(status_code=200, text=TREE_INFO_FEDORA)

        data = RepoConfigurationData()
        data.url = "http://path"
        data.proxy = "http://user:pass@example.com/proxy"

        self.metadata.load_data(data)

        session_getter.assert_called_once_with(
            "http://path/.treeinfo",
            headers={"user-agent": "anaconda (anaconda)/bluesky"},
            proxies={
                'http': 'http://user:pass@example.com:3128',
                'https': 'http://user:pass@example.com:3128',
                'ftp': 'http://user:pass@example.com:3128'
            },
            verify=True,
            cert=None,
            timeout=NETWORK_CONNECTION_TIMEOUT
        )

    @patch("requests.Session.get")
    def test_load_data_invalid_proxy(self, session_getter):
        """Test the load_data method with invalid proxy configuration."""
        session_getter.return_value.__enter__.return_value = \
            Mock(status_code=200, text=TREE_INFO_FEDORA)

        data = RepoConfigurationData()
        data.url = "http://path"
        data.proxy = "@:/invalid"

        self.metadata.load_data(data)

        session_getter.assert_called_once_with(
            "http://path/.treeinfo",
            headers={"user-agent": "anaconda (anaconda)/bluesky"},
            proxies={},
            verify=True,
            cert=None,
            timeout=NETWORK_CONNECTION_TIMEOUT
        )

    def test_generate_treeinfo_repository_fedora(self):
        """Test the generate_treeinfo_repository function with Fedora repos."""
        root_url = self._load_treeinfo(TREE_INFO_FEDORA)
        repo_mds = self.metadata.repositories
        assert len(repo_mds) == 1

        original = RepoConfigurationData()
        original.name = "anaconda"
        original.url = root_url
        original.proxy = "http://proxy"
        original.cost = 50
        original.excluded_packages = ["p1", "p2"]
        original.included_packages = ["p2", "p3"]
        original.ssl_verification_enabled = False
        original.ssl_configuration.ca_cert_path = "file.cert"
        original.ssl_configuration.client_key_path = "client.key"
        original.ssl_configuration.client_cert_path = "client.cert"
        original.installation_enabled = True

        everything = RepoConfigurationData()
        everything.origin = REPO_ORIGIN_TREEINFO
        everything.name = "Everything"
        everything.enabled = True
        everything.url = root_url
        everything.proxy = "http://proxy"
        everything.cost = 50
        everything.excluded_packages = ["p1", "p2"]
        everything.included_packages = ["p2", "p3"]
        everything.ssl_verification_enabled = False
        everything.ssl_configuration.ca_cert_path = "file.cert"
        everything.ssl_configuration.client_key_path = "client.key"
        everything.ssl_configuration.client_cert_path = "client.cert"
        everything.installation_enabled = False

        generated = generate_treeinfo_repository(original, repo_mds[0])
        assert compare_data(generated, everything)

    def test_generate_treeinfo_repository_rhel(self):
        """Test the generate_treeinfo_repository function with RHEL repos."""
        root_url = self._load_treeinfo(TREE_INFO_RHEL)
        repo_mds = self.metadata.repositories
        assert len(repo_mds) == 2

        original = RepoConfigurationData()
        original.name = "anaconda"
        original.url = root_url

        appstream = RepoConfigurationData()
        appstream.origin = REPO_ORIGIN_TREEINFO
        appstream.name = "AppStream"
        appstream.enabled = True
        appstream.url = "file:///tmp/appstream"

        baseos = RepoConfigurationData()
        baseos.origin = REPO_ORIGIN_TREEINFO
        baseos.name = "BaseOS"
        baseos.enabled = True
        baseos.url = "file:///tmp/baseos"

        generated = generate_treeinfo_repository(original, repo_mds[0])
        assert compare_data(generated, appstream)

        generated = generate_treeinfo_repository(original, repo_mds[1])
        assert compare_data(generated, baseos)

    @patch("pyanaconda.modules.payloads.payload.dnf.tree_info.conf")
    def test_generate_treeinfo_repository_custom(self, mock_conf):
        """Test the generate_treeinfo_repository function with custom repos."""
        mock_conf.payload.enabled_repositories_from_treeinfo = ["variant"]
        root_url = self._load_treeinfo(TREE_INFO_CUSTOM)
        repo_mds = self.metadata.repositories

        # Anaconda ignores addons and child variants.
        assert len(repo_mds) == 2

        original = RepoConfigurationData()
        original.name = "anaconda"
        original.url = root_url

        optional = RepoConfigurationData()
        optional.origin = REPO_ORIGIN_TREEINFO
        optional.name = "MyOptional"
        optional.enabled = False
        optional.url = root_url + "/optional"

        variant = RepoConfigurationData()
        variant.origin = REPO_ORIGIN_TREEINFO
        variant.name = "MyVariant"
        variant.enabled = True
        variant.url = root_url + "/variant"

        generated = generate_treeinfo_repository(original, repo_mds[0])
        assert compare_data(generated, optional)

        generated = generate_treeinfo_repository(original, repo_mds[1])
        assert compare_data(generated, variant)

    def test_update_treeinfo_repositories(self):
        """Test the update_treeinfo_repositories function."""
        r1 = RepoConfigurationData()
        r1.name = "r1"
        r1.url = "http://u1"

        r2 = RepoConfigurationData()
        r2.name = "r2"
        r2.url = "http://u2"

        t1 = RepoConfigurationData()
        t1.origin = REPO_ORIGIN_TREEINFO
        t1.name = "t1"
        t1.url = "http://u3"

        t2 = RepoConfigurationData()
        t2.origin = REPO_ORIGIN_TREEINFO
        t2.name = "t2"
        t2.url = "http://u4"

        n1 = RepoConfigurationData()
        n1.origin = REPO_ORIGIN_TREEINFO
        n1.name = "t1"
        n1.url = "http://u5"

        n2 = RepoConfigurationData()
        n2.origin = REPO_ORIGIN_TREEINFO
        n2.name = "t2"
        n2.url = "http://u6"

        n3 = RepoConfigurationData()
        n3.origin = REPO_ORIGIN_TREEINFO
        n3.name = "t3"
        n3.url = "http://u2"

        # Check removal of previous treeinfo repositories.
        assert update_treeinfo_repositories([], []) == []
        assert update_treeinfo_repositories([t1, t2], []) == []
        assert update_treeinfo_repositories([r1, r2], []) == [r1, r2]
        assert update_treeinfo_repositories([r1, t1, r2, t2], []) == [r1, r2]

        # Check inclusion of new treeinfo repositories.
        assert update_treeinfo_repositories([], [n1, n2]) == [n1, n2]
        assert update_treeinfo_repositories([t1, t2], [n1, n2]) == [n1, n2]
        assert update_treeinfo_repositories([r1, r2], [n1, n2]) == [r1, r2, n1, n2]
        assert update_treeinfo_repositories([r1, t1, r2, t2], [n1, n2]) == [r1, r2, n1, n2]

        # Check skipped new treeinfo repositories.
        assert update_treeinfo_repositories([r1, r2, t1], [n1, n2, n3]) == [r1, r2, n1, n2]

        # Check disabled treeinfo repositories with the same name.
        assert n1.enabled and n2.enabled and n3.enabled

        t1.enabled = False
        assert update_treeinfo_repositories([r1, t1, t2], [n1, n2, n3]) == [r1, n1, n2, n3]
        assert not n1.enabled and n2.enabled and n3.enabled

        t2.enabled = False
        assert update_treeinfo_repositories([r1, t1, t2], [n1, n2, n3]) == [r1, n1, n2, n3]
        assert not n1.enabled and not n2.enabled and n3.enabled


class LoadTreeInfoMetadataTaskTestCase(unittest.TestCase):
    """Test the LoadTreeInfoMetadataTask class."""

    def _run_task(self, data, content):
        """Run the LoadTreeInfoMetadataTask task."""

        def load_data(m, d):
            return m._load_tree_info(
                root_url=d.url,
                file_content=content
            )

        with patch.object(TreeInfoMetadata, 'load_data', autospec=True) as loader:
            loader.side_effect = load_data
            task = LoadTreeInfoMetadataTask(data)
            return task.run()

    def test_no_metadata(self):
        """Run the task with no available metadata."""
        data = RepoConfigurationData()
        task = LoadTreeInfoMetadataTask(data)
        result = task.run()

        assert isinstance(result, LoadTreeInfoMetadataResult)
        assert result.release_version is None
        assert result.repository_data is None
        assert result.treeinfo_repositories == []

    def test_fedora_metadata(self):
        """Run the task with Fedora metadata."""
        data = RepoConfigurationData()
        data.ssl_verification_enabled = False
        data.url = "http://repo"
        data.proxy = "http://proxy"

        # The root repository will be the new base repo.
        root = RepoConfigurationData()
        root.origin = REPO_ORIGIN_TREEINFO
        root.ssl_verification_enabled = False
        root.name = "Everything"
        root.url = "http://repo"
        root.proxy = "http://proxy"

        result = self._run_task(data, content=TREE_INFO_FEDORA)

        assert isinstance(result, LoadTreeInfoMetadataResult)
        assert result.release_version == "34"
        assert compare_data(result.repository_data, root)
        assert result.treeinfo_repositories == []

    def test_rhel_metadata(self):
        """Run the task with RHEL metadata."""
        data = RepoConfigurationData()
        data.ssl_verification_enabled = False
        data.url = "http://repo/unified"
        data.proxy = "http://proxy"

        # The BaseOs repository will be the new base repo.
        baseos = RepoConfigurationData()
        baseos.origin = REPO_ORIGIN_TREEINFO
        baseos.ssl_verification_enabled = False
        baseos.name = "BaseOS"
        baseos.url = "http://repo/baseos"
        baseos.proxy = "http://proxy"

        appstream = RepoConfigurationData()
        appstream.origin = REPO_ORIGIN_TREEINFO
        appstream.ssl_verification_enabled = False
        appstream.name = "AppStream"
        appstream.url = "http://repo/appstream"
        appstream.proxy = "http://proxy"

        result = self._run_task(data, content=TREE_INFO_RHEL)

        assert isinstance(result, LoadTreeInfoMetadataResult)
        assert result.release_version == "8.5"
        assert compare_data(result.repository_data, baseos)
        assert len(result.treeinfo_repositories) == 1
        assert compare_data(result.treeinfo_repositories[0], appstream)

    @patch("pyanaconda.modules.payloads.payload.dnf.tree_info.conf")
    def test_custom_metadata(self, mock_conf):
        """Run the task with custom metadata."""
        mock_conf.payload.enabled_repositories_from_treeinfo = ["variant"]

        # The original repository will be the base repo.
        data = RepoConfigurationData()
        data.ssl_verification_enabled = False
        data.url = "http://repo"
        data.proxy = "http://proxy"

        optional = RepoConfigurationData()
        optional.origin = REPO_ORIGIN_TREEINFO
        optional.ssl_verification_enabled = False
        optional.name = "MyOptional"
        optional.url = "http://repo/optional"
        optional.proxy = "http://proxy"
        optional.enabled = False

        variant = RepoConfigurationData()
        variant.origin = REPO_ORIGIN_TREEINFO
        variant.ssl_verification_enabled = False
        variant.name = "MyVariant"
        variant.url = "http://repo/variant"
        variant.proxy = "http://proxy"
        variant.enabled = True

        result = self._run_task(data, content=TREE_INFO_CUSTOM)

        assert isinstance(result, LoadTreeInfoMetadataResult)
        assert result.release_version == "1.0"
        assert compare_data(result.repository_data, data)
        assert len(result.treeinfo_repositories) == 2
        assert compare_data(result.treeinfo_repositories[0], optional)
        assert compare_data(result.treeinfo_repositories[1], variant)
