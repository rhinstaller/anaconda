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

from pyanaconda.modules.payloads.source.utils import is_valid_install_disk


class IsValidMethodTestCase(unittest.TestCase):

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
