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
import pytest
import unittest

from unittest.mock import patch, Mock

from pyanaconda.core.constants import URL_TYPE_METALINK, NETWORK_CONNECTION_TIMEOUT
from pyanaconda.modules.common.structures.payload import RepoConfigurationData
from pyanaconda.modules.payloads.payload.dnf.tree_info import TreeInfoMetadata, NoTreeInfoError, \
    InvalidTreeInfoError


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
        assert self.metadata.get_base_repo_url() == ""

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

    def test_get_base_repo_url(self):
        """Test the get_base_repo_url method."""
        # Use the root repository.
        root_url = self._load_treeinfo(TREE_INFO_FEDORA)
        assert self.metadata.get_base_repo_url() == root_url

        # Use the base repository.
        self._load_treeinfo(TREE_INFO_RHEL)
        assert self.metadata.get_base_repo_url() == "file:///tmp/baseos"

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
                'https': 'http://user:pass@example.com:3128'
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
