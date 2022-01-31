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
import unittest
from textwrap import dedent

import pytest
from pyanaconda.core.kickstart.specification import KickstartSpecificationHandler, \
    KickstartSpecificationParser
from pyanaconda.kickstart import AnacondaKickstartSpecification, RepoData
from pyanaconda.modules.common.structures.payload import RepoConfigurationData
from pyanaconda.modules.payloads.kickstart import convert_ks_repo_to_repo_data, \
    convert_repo_data_to_ks_repo


class RepoConfigurationTestCase(unittest.TestCase):
    """Test the utilities for the repo configuration data."""

    def setUp(self):
        """Set up the test."""
        self.repositories = []

    def _test_kickstart(self, ks_in, ks_out):
        """Simulate the kickstart test.

        FIXME: This is a temporary workaround.
        """
        spec = AnacondaKickstartSpecification

        # Parse a kickstart string.
        ks_in = dedent(ks_in).strip()
        handler = KickstartSpecificationHandler(spec)
        parser = KickstartSpecificationParser(handler, spec)
        parser.readKickstartFromString(ks_in)

        self.repositories = list(map(
            convert_ks_repo_to_repo_data,
            handler.repo.dataList()
        ))

        # Verify the DBus data.
        RepoConfigurationData.to_structure_list(self.repositories)

        # Generate a kickstart string.
        ks_out = dedent(ks_out).strip()
        handler = KickstartSpecificationHandler(spec)

        for repo_data in self.repositories:
            ks_repo = convert_repo_data_to_ks_repo(repo_data)
            handler.repo.dataList().append(ks_repo)

        ks_generated = str(handler).strip()
        assert ks_generated == ks_out

    def test_repo_convert_invalid(self):
        """Test the conversion functions with an invalid input."""
        with pytest.raises(ValueError):
            convert_ks_repo_to_repo_data(None)

        with pytest.raises(ValueError):
            convert_repo_data_to_ks_repo(None)

    def test_repo_updates(self):
        """Test the updates repo command."""
        ks_in = """
        repo --name=updates
        """
        ks_out = """
        repo --name="updates"
        """
        self._test_kickstart(ks_in, ks_out)

    def test_repo_baseurl(self):
        ks_in = """
        repo --name=test --baseurl http://url
        """
        ks_out = """
        repo --name="test" --baseurl=http://url
        """
        self._test_kickstart(ks_in, ks_out)

    def test_repo_mirrorlist(self):
        ks_in = """
        repo --name=test --mirrorlist http://mirror
        """
        ks_out = """
        repo --name="test" --mirrorlist=http://mirror
        """
        self._test_kickstart(ks_in, ks_out)

    def test_repo_metalink(self):
        ks_in = """
        repo --name=test --metalink http://metalink
        """
        ks_out = """
        repo --name="test"  --metalink=http://metalink
        """
        self._test_kickstart(ks_in, ks_out)

    def test_repo_proxy(self):
        ks_in = """
        repo --name=test --baseurl http://url  --proxy http://user:pass@example.com:3128
        """
        ks_out = """
        repo --name="test" --baseurl=http://url --proxy="http://user:pass@example.com:3128"
        """
        self._test_kickstart(ks_in, ks_out)

    def test_repo_cost(self):
        ks_in = """
        repo --name=test --baseurl http://url  --cost 123
        """
        ks_out = """
        repo --name="test" --baseurl=http://url --cost=123
        """
        self._test_kickstart(ks_in, ks_out)

    def test_repo_packages(self):
        ks_in = """
        repo --name=test --baseurl http://url --includepkgs p1,p2 --excludepkgs p3,p4
        """
        ks_out = """
        repo --name="test" --baseurl=http://url --includepkgs="p1,p2" --excludepkgs="p3,p4"
        """
        self._test_kickstart(ks_in, ks_out)
        assert self.repositories[0].included_packages == ["p1", "p2"]
        assert self.repositories[0].excluded_packages == ["p3", "p4"]

    def test_repo_no_ssl_verification(self):
        ks_in = """
        repo --name=test --baseurl http://url --noverifyssl
        """
        ks_out = """
        repo --name="test" --baseurl=http://url --noverifyssl
        """
        self._test_kickstart(ks_in, ks_out)
        assert self.repositories[0].ssl_verification_enabled is False

    def test_repo_ssl_configuration(self):
        ks_in = """
        repo --name=test --baseurl http://url --sslcacert x.cert --sslclientcert private-x.cert --sslclientkey x.key
        """
        ks_out = """
        repo --name="test" --baseurl=http://url --sslcacert="x.cert" --sslclientcert="private-x.cert" --sslclientkey="x.key"
        """
        self._test_kickstart(ks_in, ks_out)
        assert self.repositories[0].ssl_verification_enabled is True

    def test_repo_install(self):
        ks_in = """
        repo --name=test --baseurl http://url --install
        """
        ks_out = """
        repo --name="test" --baseurl=http://url --install
        """
        self._test_kickstart(ks_in, ks_out)

    def test_convert_repo_enabled(self):
        """Test the conversion of the enabled attribute."""
        ks_repo = RepoData()
        repo_data = convert_ks_repo_to_repo_data(ks_repo)
        assert repo_data.enabled is True

        ks_repo = convert_repo_data_to_ks_repo(repo_data)
        assert ks_repo.enabled is True

        ks_repo.enabled = False
        repo_data = convert_ks_repo_to_repo_data(ks_repo)
        assert repo_data.enabled is False

        ks_repo = convert_repo_data_to_ks_repo(repo_data)
        assert ks_repo.enabled is False
