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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Authors: Jiri Konecny <jkonecny@redhat.com>
#
import unittest
import pytest

import pyanaconda.core.payload as util
from pyanaconda.core.payload import parse_hdd_url


class PayloadUtilsTests(unittest.TestCase):

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

        assert util.create_nfs_url("host", "") == "nfs:host:"
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
