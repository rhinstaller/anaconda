#
# Copyright (C) 2020  Red Hat, Inc.
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

import pytest
from dasbus.structure import compare_data
from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.core.constants import SOURCE_TYPE_URL
from pyanaconda.modules.common.constants.interfaces import PAYLOAD_SOURCE_REPOSITORY
from pyanaconda.modules.common.errors.general import InvalidValueError
from pyanaconda.modules.common.errors.payload import SourceSetupError
from pyanaconda.modules.common.structures.payload import RepoConfigurationData
from pyanaconda.modules.payloads.source.url.url import URLSourceModule
from tests.unit_tests.pyanaconda_tests import check_dbus_property


class URLSourceInterfaceTestCase(unittest.TestCase):

    def setUp(self):
        """Set up the test."""
        self.module = URLSourceModule()
        self.interface = self.module.for_publication()

    def _check_dbus_property(self, property_name, in_value):
        """Check a DBus property."""
        check_dbus_property(
            PAYLOAD_SOURCE_REPOSITORY,
            self.interface,
            property_name,
            in_value
        )

    def test_type(self):
        """Test URL source has a correct type specified."""
        assert self.interface.Type == SOURCE_TYPE_URL

    def test_description(self):
        """Test URL source description."""
        assert self.interface.Description == ""

        self.module.configuration.url = "http://test"
        assert self.interface.Description == "http://test"

    def test_set_invalid_url_protocol(self):
        """Test a configuration with an invalid protocol."""
        data = RepoConfigurationData()
        data.url = "unknown://test"

        with pytest.raises(InvalidValueError) as cm:
            self.interface.Configuration = \
                RepoConfigurationData.to_structure(data)

        assert str(cm.value) == "Invalid protocol of an URL source: 'unknown://test'"

    def test_set_invalid_url_type(self):
        """Test a configuration with an invalid URL type."""
        data = RepoConfigurationData()
        data.url = "http://test"
        data.type = "DOES-NOT-EXISTS"

        with pytest.raises(InvalidValueError) as cm:
            self.interface.Configuration = \
                RepoConfigurationData.to_structure(data)

        assert str(cm.value) == "Invalid URL type of an URL source: 'DOES-NOT-EXISTS'"

    def test_set_invalid_proxy_properties(self):
        """Test a configuration with an invalid proxy."""
        data = RepoConfigurationData()
        data.url = "http://test"
        data.proxy = "http:///invalid"

        with pytest.raises(InvalidValueError) as cm:
            self.interface.Configuration = \
                RepoConfigurationData.to_structure(data)

        assert str(cm.value) == "Invalid proxy of an URL source: 'http:///invalid'"

    def test_configuration_property(self):
        """Test the Configuration property."""
        ssl_data = {
            "ca-cert-path": get_variant(Str, "file:///ca_cert/path"),
            "client-cert-path": get_variant(Str, "file:///client/cert/path"),
            "client-key-path": get_variant(Str, "file:///to/client/key")
        }
        data = {
            "name": get_variant(Str, "My repository example"),
            "origin": get_variant(Str, "USER"),
            'enabled': get_variant(Bool, False),
            "url": get_variant(Str, "http://test"),
            "type": get_variant(Str, "BASEURL"),
            "ssl-verification-enabled": get_variant(Bool, False),
            "ssl-configuration": get_variant(Structure, ssl_data),
            "proxy": get_variant(Str, "http://user:pass@test/proxy"),
            "cost": get_variant(Int, 2000),
            "excluded-packages": get_variant(List[Str], [
                "foo", "bar", "foobar"
            ]),
            "included-packages": get_variant(List[Str], [
                "python*", "perl", "rattlesnake"
            ]),
            "installation-enabled": get_variant(Bool, True),
        }

        self._check_dbus_property(
            "Configuration",
            data
        )


class URLSourceTestCase(unittest.TestCase):
    """Test the URL source module."""

    def setUp(self):
        self.module = URLSourceModule()

    def test_network_required(self):
        """Test the property network_required."""
        assert self.module.network_required is False

        self.module.configuration.url = "http://my/path"
        assert self.module.network_required is True

        self.module.configuration.url = "https://my/path"
        assert self.module.network_required is True

        self.module.configuration.url = "file://my/path"
        assert self.module.network_required is False

        self.module.configuration.url = "ftp://my/path"
        assert self.module.network_required is True

    def test_required_space(self):
        """Test the required_space property."""
        assert self.module.required_space == 0

    def test_ready_state(self):
        """Check ready state of URL source.

        It will be always True there is no state.
        """
        assert self.module.get_state()

    def test_set_up_with_tasks(self):
        """Get set up tasks for the URL source.

        No task is required. Will be an empty list.
        """
        assert self.module.set_up_with_tasks() == []

    def test_tear_down_with_tasks(self):
        """Get tear down tasks for the URL source.

        No task is required. Will be an empty list.
        """
        assert self.module.tear_down_with_tasks() == []

    def test_no_repository_configuration(self):
        """Test a missing repository configuration."""
        with pytest.raises(SourceSetupError) as cm:
            assert self.module.repository

        assert str(cm.value) == "The repository configuration is unavailable."

    def test_repository_configuration(self):
        """Test the repository configuration."""
        data = RepoConfigurationData()
        data.url = "http://test"
        self.module.set_configuration(data)

        assert self.module.repository
        assert self.module.repository is not data
        assert compare_data(self.module.repository, data)

    def test_repr(self):
        """Test the string representation of the URL source."""
        assert repr(self.module) == "Source(type='URL', url='')"

        self.module.configuration.url = "http://test"
        assert repr(self.module) == "Source(type='URL', url='http://test')"
