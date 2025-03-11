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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import unittest
from textwrap import dedent

from pyanaconda.core.constants import REPO_ORIGIN_SYSTEM, REPO_ORIGIN_TREEINFO
from pyanaconda.modules.common.structures.payload import RepoConfigurationData
from pyanaconda.ui.gui.spokes.lib.installation_source_helpers import (
    generate_repository_description,
    get_invalid_repository_message,
    get_unique_repo_name,
    validate_additional_repositories,
    validate_proxy,
    validate_repo_name,
    validate_repo_url,
)
from pyanaconda.ui.helpers import InputCheck


class InstallationSourceUtilsTestCase(unittest.TestCase):
    """Test functions used by the Installation Source spoke."""

    def test_get_unique_repo_name(self):
        """Test the get_unique_repo_name function."""
        assert "New_Repository" == get_unique_repo_name()
        assert "New_Repository" == get_unique_repo_name([
            "New_Repository_1",
        ])
        assert "New_Repository" == get_unique_repo_name([
            "New_Repository_1",
            "New_Repository_2",
        ])
        assert "New_Repository_1" == get_unique_repo_name([
            "New_Repository"
        ])
        assert "New_Repository_2" == get_unique_repo_name([
            "New_Repository",
            "New_Repository_1",
        ])
        assert "New_Repository_3" == get_unique_repo_name([
            "New_Repository",
            "New_Repository_1",
            "New_Repository_2",
        ])
        assert "New_Repository_4" == get_unique_repo_name([
            "New_Repository",
            "New_Repository_3",
        ])

    def test_generate_repository_description(self):
        """Test the generate_repository_description function."""
        r1 = RepoConfigurationData()
        expected = dedent("""
        {
        cost = 1000
        enabled = True
        excluded-packages = []
        included-packages = []
        installation-enabled = False
        name = ''
        origin = 'USER'
        proxy = ''
        ssl-configuration = SSLConfigurationData()
        ssl-verification-enabled = True
        type = 'BASEURL'
        url = ''
        }
        """)

        assert generate_repository_description(r1).strip() == expected.strip()

        r2 = RepoConfigurationData()
        r2.name = "my-repository"
        r2.url = "http://my/repository"
        r2.proxy = "http://my/proxy"

        expected = dedent("""
        {
        cost = 1000
        enabled = True
        excluded-packages = []
        included-packages = []
        installation-enabled = False
        name = 'my-repository'
        origin = 'USER'
        proxy = 'http://my/proxy'
        ssl-configuration = SSLConfigurationData()
        ssl-verification-enabled = True
        type = 'BASEURL'
        url = 'http://my/repository'
        }
        """)

        assert generate_repository_description(r2).strip() == expected.strip()

    def test_validate_repo_name(self):
        """Test the validate_repo_name function."""
        assert validate_repo_name("New_Repository_1") == InputCheck.CHECK_OK
        assert validate_repo_name("AppStream") == InputCheck.CHECK_OK
        assert validate_repo_name("my_repo") == InputCheck.CHECK_OK
        assert validate_repo_name("my_repo", conflicting_names=["another"]) == InputCheck.CHECK_OK

        msg = "Empty repository name"
        assert validate_repo_name("") == msg

        msg = "Invalid repository name"
        assert validate_repo_name("invalid repo") == msg
        assert validate_repo_name("repo(invalid)") == msg

        msg = "Repository name conflicts with internal repository name"
        assert validate_repo_name("anaconda") == msg
        assert validate_repo_name("rawhide") == msg
        assert validate_repo_name("my_repo", conflicting_names=["my_repo"]) == msg

        msg = "Duplicate repository names"
        assert validate_repo_name("r1", occupied_names=[]) == InputCheck.CHECK_OK
        assert validate_repo_name("r1", occupied_names=["r1", "r2"]) == InputCheck.CHECK_OK
        assert validate_repo_name("r1", occupied_names=["r1", "r2", "r1"]) == msg

    def test_validate_repo_url(self):
        """Test the validate_repo_url function."""
        assert validate_repo_url("") == "Empty URL"
        assert validate_repo_url("test") == "Invalid protocol"

        assert validate_repo_url("file:") == InputCheck.CHECK_OK
        assert validate_repo_url("file:///path") == InputCheck.CHECK_OK

        assert validate_repo_url("hd:") == InputCheck.CHECK_OK
        assert validate_repo_url("hd:/dev/test:/path") == InputCheck.CHECK_OK

        assert validate_repo_url("nfs:") == "Empty server"
        assert validate_repo_url("nfs:$%#") == "Invalid server"
        assert validate_repo_url("nfs:server") == "Empty path"
        assert validate_repo_url("nfs:server:/path") == InputCheck.CHECK_OK
        assert validate_repo_url("nfs:nolock,timeo=50:server:/path") == InputCheck.CHECK_OK

        assert validate_repo_url("http:") == "Invalid URL"
        assert validate_repo_url("http://repo/$%#") == "Invalid URL"
        assert validate_repo_url("http://repo/url") == InputCheck.CHECK_OK

        assert validate_repo_url("https:") == "Invalid URL"
        assert validate_repo_url("https://repo/url") == InputCheck.CHECK_OK

        assert validate_repo_url("ftp:") == "Invalid URL"
        assert validate_repo_url("ftp://repo/url") == InputCheck.CHECK_OK

    def test_validate_proxy_url(self):
        """Test the validate_proxy function."""
        assert validate_proxy("") == InputCheck.CHECK_OK

        assert validate_proxy("test:") == "Invalid proxy URL"
        assert validate_proxy("http:") == "Invalid proxy URL"
        assert validate_proxy("http://$%#.com") == "Invalid proxy URL"
        assert validate_proxy("http://example.com") == InputCheck.CHECK_OK
        assert validate_proxy("http://example.com:3128") == InputCheck.CHECK_OK
        assert validate_proxy("http://user:pass@example.com:3128") == InputCheck.CHECK_OK

        assert validate_proxy("test://examples.com") == "Invalid proxy protocol: test://"
        assert validate_proxy("https://example.com") == InputCheck.CHECK_OK
        assert validate_proxy("ftp://example.com") == InputCheck.CHECK_OK

        msg = "Extra characters in proxy URL"
        assert validate_proxy("http://proxy.example.com:8080/") == InputCheck.CHECK_OK
        assert validate_proxy("http://proxy.example.com:8080/path") == msg
        assert validate_proxy("http://proxy.example.com:8080?query") == msg
        assert validate_proxy("http://proxy.example.com:8080#fragment") == msg

        msg = "Proxy authentication data duplicated"
        assert validate_proxy("http://user:pass@example.com") == InputCheck.CHECK_OK
        assert validate_proxy("http://user:pass@example.com", authentication=False) == msg
        assert validate_proxy("http://user@example.com", authentication=False) == msg
        assert validate_proxy("http://example.com", authentication=False) == InputCheck.CHECK_OK

    def test_get_invalid_repository_message(self):
        """Test the get_invalid_repository_message function."""
        assert get_invalid_repository_message("my_repo", "This is wrong!") == \
            "The 'my_repo' repository is invalid: This is wrong!"

    def test_validate_additional_repositories(self):
        """Test the validate_additional_repositories function."""
        r1 = RepoConfigurationData()
        r1.name = "r1"
        r1.url = "http://repo"
        r1.proxy = "http://proxy"

        r2 = RepoConfigurationData()
        r2.name = "r2"
        r2.url = "nfs:server:path"

        r3 = RepoConfigurationData()
        r3.name = "r3"
        r3.url = "invalid"

        r4 = RepoConfigurationData()
        r4.name = "r4"
        r4.url = "ftp://repo"
        r4.proxy = "$#!"

        r5 = RepoConfigurationData()
        r5.name = "r5"

        report = validate_additional_repositories([])
        assert report.get_messages() == []

        report = validate_additional_repositories([r1])
        assert report.get_messages() == []

        report = validate_additional_repositories(
            additional_repositories=[r1, r2, r3, r4, r5],
            conflicting_names=["r2", "r6", "r7", "r8"]
        )
        assert report.get_messages() == [
            "The 'r2' repository is invalid: Repository name"
            " conflicts with internal repository name",
            "The 'r3' repository is invalid: Invalid protocol",
            "The 'r4' repository is invalid: Invalid proxy URL",
            "The 'r5' repository is invalid: Empty URL",
        ]

        r2.name = "r20"
        r3.enabled = False
        r4.origin = REPO_ORIGIN_TREEINFO
        r5.origin = REPO_ORIGIN_SYSTEM

        report = validate_additional_repositories(
            additional_repositories=[r1, r2, r3, r4, r5],
            conflicting_names=["r2", "r6", "r7", "r8"]
        )
        assert report.get_messages() == []
