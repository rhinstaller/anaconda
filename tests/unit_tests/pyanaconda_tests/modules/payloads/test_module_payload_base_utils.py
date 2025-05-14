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
import os
from tempfile import TemporaryDirectory
from textwrap import dedent
from unittest.case import TestCase
from unittest.mock import patch

from pyanaconda.modules.payloads.base.utils import (
    create_root_dir,
    get_dir_size,
    sort_kernel_version_list,
    write_module_blacklist,
)


class PayloadBaseUtilsTest(TestCase):

    def test_create_root(self):
        """Test payload create root directory function."""
        with TemporaryDirectory() as temp:
            create_root_dir(temp)

            root_dir = os.path.join(temp, "/root")

            assert os.path.isdir(root_dir) is True

    @patch('pyanaconda.modules.payloads.base.utils.kernel_arguments',
           {"modprobe.blacklist": "mod1 mod2 nonono_mod"})
    def test_write_module_blacklist(self):
        """Test write kernel module blacklist to the install root."""
        with TemporaryDirectory() as temp:
            write_module_blacklist(temp)

            blacklist_file = os.path.join(temp, "etc/modprobe.d/anaconda-blacklist.conf")

            assert os.path.isfile(blacklist_file) is True

            with open(blacklist_file, "rt") as f:
                expected_content = """
                # Module blacklists written by anaconda
                blacklist mod1
                blacklist mod2
                blacklist nonono_mod
                """
                assert dedent(expected_content).lstrip() == f.read()

    @patch('pyanaconda.modules.payloads.base.utils.kernel_arguments', {})
    def test_write_empty_module_blacklist(self):
        """Test write kernel module blacklist to the install root -- empty list."""
        with TemporaryDirectory() as temp:
            write_module_blacklist(temp)

            blacklist_file = os.path.join(temp, "etc/modprobe.d/anaconda-blacklist.conf")

            assert os.path.isfile(blacklist_file) is False

    def test_get_dir_size(self):
        """Test the get_dir_size function."""

        # dev null should have a size == 0
        assert get_dir_size('/dev/null') == 0

        # incorrect path should also return 0
        assert get_dir_size('/dev/null/foo') == 0

        # check if an int is always returned
        assert isinstance(get_dir_size('/dev/null'), int)
        assert isinstance(get_dir_size('/dev/null/foo'), int)

        # TODO: mock some dirs and check if their size is
        # computed correctly

    def test_sort_kernel_version_list(self):
        """Test the sort_kernel_version_list function."""
        # Test fake versions.
        kernel_version_list = [
            '9.1.1-100.f1',
            '10.1.1-100.f1',
            '1.9.1-100.f1',
            '1.10.1-100.f1',
            '1.1.9-100.f1',
            '1.1.10-100.f1',
            '1.1.1-999.f1',
            '1.1.1-1000.f1',
            '1.1.1-100.f1',
            '1.1.1-100.f2',
        ]

        sort_kernel_version_list(kernel_version_list)
        assert kernel_version_list == [
            '1.1.1-100.f1',
            '1.1.1-100.f2',
            '1.1.1-999.f1',
            '1.1.1-1000.f1',
            '1.1.9-100.f1',
            '1.1.10-100.f1',
            '1.9.1-100.f1',
            '1.10.1-100.f1',
            '9.1.1-100.f1',
            '10.1.1-100.f1'
        ]

        # Test real versions.
        kernel_version_list = [
            '5.8.16-200.fc32.x86_64',
            '5.8.18-200.fc32.x86_64',
            '5.10.0-0.rc4.78.fc34.x86_64',
            '5.9.8-100.fc33.x86_64',
            '5.8.18-300.fc33.x86_64',
            '5.8.15-201.fc32.x86_64',
            '5.9.8-200.fc33.x86_64',
        ]

        sort_kernel_version_list(kernel_version_list)
        assert kernel_version_list == [
            '5.8.15-201.fc32.x86_64',
            '5.8.16-200.fc32.x86_64',
            '5.8.18-200.fc32.x86_64',
            '5.8.18-300.fc33.x86_64',
            '5.9.8-100.fc33.x86_64',
            '5.9.8-200.fc33.x86_64',
            '5.10.0-0.rc4.78.fc34.x86_64'
        ]
