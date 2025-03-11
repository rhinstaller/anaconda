#
# Copyright (C) 2018  Red Hat, Inc.
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
# Authors: Jiri Konecny <jkonecny@redhat.com>
#
import unittest
from functools import partial

import pytest

import pyanaconda.core.payload as util
from pyanaconda.core.constants import (
    SOURCE_TYPE_CDROM,
    SOURCE_TYPE_HDD,
    SOURCE_TYPE_HMC,
    SOURCE_TYPE_NFS,
    SOURCE_TYPE_URL,
)
from pyanaconda.core.payload import create_hdd_url, parse_hdd_url
from pyanaconda.modules.common.constants.services import PAYLOADS
from pyanaconda.modules.common.structures.payload import RepoConfigurationData
from pyanaconda.payload.dnf import DNFPayload
from tests.unit_tests.pyanaconda_tests import patch_dbus_get_proxy_with_cache


class PayloadUtilsTests(unittest.TestCase):
    """Test the payload utilities."""

    def test_parse_nfs_url(self):
        """Test parseNfsUrl."""
        # empty NFS url should return 3 blanks
        assert util.parse_nfs_url("") == ("", "", "")

        # the string is delimited by :, there is one prefix and 3 parts,
        # the prefix is discarded and all parts after the 3th part
        # are also discarded
        assert util.parse_nfs_url("nfs:options:host:path") == \
            ("options", "host", "path")
        assert util.parse_nfs_url("nfs:options:host:path:foo:bar") == \
            ("options", "host", "path")

        # if there is only prefix & 2 parts,
        # the two parts are host and path
        assert util.parse_nfs_url("nfs://host:path") == \
            ("", "host", "path")
        assert util.parse_nfs_url("nfs:host:path") == \
            ("", "host", "path")

        # if there is only a prefix and single part,
        # the part is the host
        assert util.parse_nfs_url("nfs://host") == \
            ("", "host", "")
        assert util.parse_nfs_url("nfs:host") == \
            ("", "host", "")

    def test_create_nfs_url(self):
        """Test create_nfs_url."""

        assert util.create_nfs_url("", "") == ""
        assert util.create_nfs_url("", "", None) == ""
        assert util.create_nfs_url("", "", "") == ""

        assert util.create_nfs_url("host", "") == "nfs:host"
        assert util.create_nfs_url("host", "", "options") == "nfs:options:host:"

        assert util.create_nfs_url("host", "path") == "nfs:host:path"
        assert util.create_nfs_url("host", "/path", "options") == "nfs:options:host:/path"

        assert util.create_nfs_url("host", "/path/to/something") == \
            "nfs:host:/path/to/something"
        assert util.create_nfs_url("host", "/path/to/something", "options") == \
            "nfs:options:host:/path/to/something"

    def test_nfs_combine(self):
        """Test combination of parse and create nfs functions."""

        host = "host"
        path = "/path/to/somewhere"
        options = "options"

        url = util.create_nfs_url(host, path, options)
        assert util.parse_nfs_url(url) == (options, host, path)

        url = "nfs:options:host:/my/path"
        (options, host, path) = util.parse_nfs_url(url)
        assert util.create_nfs_url(host, path, options) == url

    def test_split_protocol(self):
        """Test split protocol test."""

        assert util.split_protocol("http://abc/cde") == ("http://", "abc/cde")
        assert util.split_protocol("https://yay/yay") == ("https://", "yay/yay")
        assert util.split_protocol("ftp://ups/spu") == ("ftp://", "ups/spu")
        assert util.split_protocol("file:///test/file") == ("file://", "/test/file")
        assert util.split_protocol("nfs:ups/spu:/abc:opts") == ("", "nfs:ups/spu:/abc:opts")
        assert util.split_protocol("http:/typo/test") == ("", "http:/typo/test")
        assert util.split_protocol("") == ("", "")

        with pytest.raises(ValueError):
            util.split_protocol("http://ftp://ups/this/is/not/correct")

    def test_parse_hdd_url(self):
        """Test the parse_hdd_url function."""
        assert parse_hdd_url("") == ("", "")
        assert parse_hdd_url("hd:test") == ("test", "")
        assert parse_hdd_url("hd:/dev/test") == ("/dev/test", "")
        assert parse_hdd_url("hd:/dev/test:relative") == ("/dev/test", "relative")
        assert parse_hdd_url("hd:/dev/test:/absolute") == ("/dev/test", "/absolute")
        assert parse_hdd_url("hd:/dev/test:relative/path") == ("/dev/test", "relative/path")
        assert parse_hdd_url("hd:/dev/test:/absolute/path") == ("/dev/test", "/absolute/path")

    def test_create_hdd_url(self):
        """Test the create_hdd_url function."""
        assert create_hdd_url("") == ""
        assert create_hdd_url("", "") == ""
        assert create_hdd_url("test") == "hd:test"
        assert create_hdd_url("/dev/test") == "hd:/dev/test"
        assert create_hdd_url("/dev/test", "relative") == "hd:/dev/test:relative"
        assert create_hdd_url("/dev/test", "/absolute") == "hd:/dev/test:/absolute"
        assert create_hdd_url("/dev/test", "relative/path") == "hd:/dev/test:relative/path"
        assert create_hdd_url("/dev/test", "/absolute/path") == "hd:/dev/test:/absolute/path"


class DNFPayloadOptionsTests(unittest.TestCase):
    """Test the DNF payload support for cmdline and boot options."""

    def _generate_id(self):
        """Generate a unique number."""
        count = 0

        while True:
            yield count
            count += 1

    def _create_source(self, source_type, source_url):
        """Create a source from the specified URL and check its type."""
        source_path = "/my/source/{}".format(str(self._generate_id()))

        payloads_proxy = PAYLOADS.get_proxy()
        payloads_proxy.CreateSource.return_value = source_path

        source_proxy = DNFPayload._create_source_from_url(source_url)
        payloads_proxy.CreateSource.assert_called_with(source_type)
        return source_proxy

    @patch_dbus_get_proxy_with_cache
    def test_create_source_from_url_invalid(self, proxy_getter):
        """Test the create_source_from_url function with invalid values."""
        with pytest.raises(ValueError) as cm:
            self._create_source(SOURCE_TYPE_HMC, "invalid:/path")

        msg = "Unknown type of the installation source: invalid:/path"
        assert str(cm.value) == msg

    @patch_dbus_get_proxy_with_cache
    def test_create_source_from_url_hmc(self, proxy_getter):
        """Test HMC sources created by the create_source_from_url function."""
        self._create_source(SOURCE_TYPE_HMC, "hmc")

    @patch_dbus_get_proxy_with_cache
    def test_create_source_from_url_cdrom(self, proxy_getter):
        """Test CDROM sources created by the create_source_from_url function."""
        self._create_source(SOURCE_TYPE_CDROM, "cdrom")
        self._create_source(SOURCE_TYPE_CDROM, "cdrom:/dev/cdrom")

    @patch_dbus_get_proxy_with_cache
    def test_create_source_from_url(self, proxy_getter):
        """Test URL sources created by the create_source_from_url function."""
        create_source = partial(self._create_source, SOURCE_TYPE_URL)

        create_source("http://server.example.com/test")
        create_source("https://server.example.com/test")
        create_source("ftp://server.example.com/test")
        create_source("file:///local/path/test")

        proxy = create_source("http://server.example.com/test")
        configuration = RepoConfigurationData.from_structure(proxy.Configuration)
        assert configuration.url == "http://server.example.com/test"

    @patch_dbus_get_proxy_with_cache
    def test_create_source_from_url_nfs(self, proxy_getter):
        """Test NFS sources created by the create_source_from_url function."""
        create_source = partial(self._create_source, SOURCE_TYPE_NFS)

        create_source("nfs://server.nfs.com:/path/on/server")
        create_source("nfs:soft,async:server.com:/path/to/install_tree")
        create_source("nfs:server.example.com:/path/to/install_tree")

        proxy = create_source("nfs://server.nfs.com:/path/on/server")
        configuration = RepoConfigurationData.from_structure(proxy.Configuration)
        assert configuration.url == "nfs://server.nfs.com:/path/on/server"

    @patch_dbus_get_proxy_with_cache
    def test_create_source_from_url_hdd(self, proxy_getter):
        """Test HDD sources created by the create_source_from_url function."""
        create_source = partial(self._create_source, SOURCE_TYPE_HDD)

        create_source("hd:/dev/sda2:/path/to/iso.iso")
        create_source("hd:LABEL=TEST:/path/to/iso.iso")
        create_source("hd:UUID=8176c7bf-04ff-403a:/path/to/iso.iso")

        proxy = create_source("hd:/dev/sda2:/path/to/iso.iso")
        configuration = RepoConfigurationData.from_structure(proxy.Configuration)
        assert configuration.url == "hd:/dev/sda2:/path/to/iso.iso"
