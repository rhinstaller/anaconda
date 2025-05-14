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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import unittest
from io import StringIO
from unittest.mock import patch

from pyanaconda.modules.payloads.source.utils import is_tar, is_valid_install_disk


class SourceUtilsTestCase(unittest.TestCase):
    """Test the source utils."""

    def test_is_tar(self):
        """Test the is_tar function."""
        assert not is_tar(None)
        assert not is_tar("")
        assert not is_tar("/my/path")
        assert not is_tar("file://my/path.")
        assert not is_tar("http://my/path.img")
        assert not is_tar("https://my/path.tarball")

        assert not is_tar("/my/tar")
        assert not is_tar("file://my/tbz")
        assert not is_tar("http://my/tgz")
        assert not is_tar("https://my/txz")
        assert not is_tar("/my/tar.bz2")
        assert not is_tar("file://my/tar.gz")
        assert not is_tar("http://my/tar.xz")

        assert is_tar("/my/path.tar")
        assert is_tar("file://my/path.tbz")
        assert is_tar("http://my/path.tgz")
        assert is_tar("https://my/path.txz")
        assert is_tar("/my/path.tar.bz2")
        assert is_tar("file://my/path.tar.gz")
        assert is_tar("http://my/path.tar.xz")


class IsValidMethodTestCase(unittest.TestCase):
    """Test the is_valid_install_disk function."""

    @patch("pyanaconda.modules.payloads.source.utils.get_arch",
           return_value="test-arch")
    @patch("pyanaconda.modules.payloads.source.utils.open",
           return_value=StringIO("timestamp\ndescription\ntest-arch\n"))
    def test_success(self, open_mock, get_arch_mock):
        """Test installation disk validation - arch match."""
        assert is_valid_install_disk("/some/dir")

    @patch("pyanaconda.modules.payloads.source.utils.get_arch",
           return_value="does-not-match")
    @patch("pyanaconda.modules.payloads.source.utils.open",
           return_value=StringIO("timestamp\ndescription\ntest-arch\n"))
    def test_fail_arch(self, open_mock, get_arch_mock):
        """Test installation disk validation - arch mismatch."""
        assert not is_valid_install_disk("/some/dir")

    @patch("pyanaconda.modules.payloads.source.utils.get_arch")
    @patch("pyanaconda.modules.payloads.source.utils.open",
           side_effect=OSError("Mockity mock"))
    def test_fail_no_file(self, open_mock, get_arch_mock):
        """Test installation disk validation - no file."""
        # the exception is caught inside - check that get_arch() is not called instead
        assert not is_valid_install_disk("/some/dir")
        get_arch_mock.assert_not_called()
