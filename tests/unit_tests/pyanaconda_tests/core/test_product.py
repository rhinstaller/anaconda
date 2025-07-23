#
# Copyright 2023 Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use, modify,
# copy, or redistribute it subject to the terms and conditions of the GNU
# General Public License v.2.  This program is distributed in the hope that it
# will be useful, but WITHOUT ANY WARRANTY expressed or implied, including the
# implied warranties of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.  Any Red Hat
# trademarks that are incorporated in the source code or documentation are not
# subject to the GNU General Public License and may only be used or replicated
# with the express permission of Red Hat, Inc.
#
# Test the Python-based signal and slot implementation.
#

import os
import unittest
import tempfile
from textwrap import dedent
from unittest.mock import mock_open, patch

from pyanaconda.core.util import make_directories
import pyanaconda.core.product  # needed for patching, see below
from pyanaconda.core.product import (
    ProductData,
    get_os_release_value,
    get_product_is_final_release,
    get_product_name,
    get_product_short_name,
    get_product_values,
    get_product_version,
    trim_product_version_for_ui,
)


class ProductHelperTestCase(unittest.TestCase):

    def test_get_os_relase_value(self):
        """Test the get_release_value function."""
        with tempfile.TemporaryDirectory() as root:
            # prepare paths
            make_directories(root + "/usr/lib")
            make_directories(root + "/etc")

            # no file
            version = get_os_release_value("VERSION_ID", root)
            assert version is None

            # backup file only
            with open(root + "/usr/lib/os-release", "w") as f:
                f.write("# blah\nVERSION_ID=foo256bar  \n VERSION_ID = wrong\n\n")
            version = get_os_release_value("VERSION_ID", root)
            assert version == "foo256bar"

            # main file and backup too
            with open(root + "/etc/os-release", "w") as f:
                f.write("# blah\nVERSION_ID=more-important\n")
            version = get_os_release_value("VERSION_ID", root)
            assert version == "more-important"

            # both, main file twice
            with open(root + "/etc/os-release", "w") as f:
                f.write("# blah\nVERSION_ID=more-important\nVERSION_ID=not-reached\n \n")
            version = get_os_release_value("VERSION_ID", root)
            assert version == "more-important"

            # quoted values
            with open(root + "/etc/os-release", "w") as f:
                f.write("PRETTY_NAME=\"Fedora 32\"\n")
            assert get_os_release_value("PRETTY_NAME", root) == "Fedora 32"

            # no files
            os.remove(root + "/usr/lib/os-release")
            os.remove(root + "/etc/os-release")
            version = get_os_release_value("VERSION_ID", root)
            assert version is None

    def test_trim_product_version_for_ui(self):
        """Test version shortening."""
        trimmed_versions = [
            ("8.0.0", "8.0"),
            ("7.6", "7.6"),
            ("7", "7"),
            ("8.0.0.1", "8.0"),
        ]

        for original, trimmed in trimmed_versions:
            assert trimmed == trim_product_version_for_ui(original)


class ProductTestCase(unittest.TestCase):
    """Test product value loading"""

    def setUp(self):
        # can't have the cache returning the same thing across all tests
        get_product_values.cache_clear()

    @classmethod
    def tearDownClass(cls):
        # invalidate cache also for all tests run after this
        get_product_values.cache_clear()

    def test_env(self):
        """Test product values loaded from environment variables."""
        FAKE_OS_RELEASE = ""
        FAKE_OS_RELEASE += 'NAME="Fedora Linux"\n'
        FAKE_OS_RELEASE += 'VERSION="41 (Workstation Edition)"\n'
        FAKE_OS_RELEASE += 'VERSION_ID="41"\n'
        FAKE_OS_RELEASE += 'RELEASE_TYPE=stable\n'
        FAKE_OS_RELEASE += 'ID=fedora\n'

        m = mock_open(read_data=FAKE_OS_RELEASE)
        with patch("builtins.open", m):
            values = get_product_values()
        expected = ProductData(True, "Fedora Linux", "41", "fedora")
        assert values == expected

        # cached values are kept within single test fixture
        assert get_product_is_final_release() is True
        assert get_product_name() == "Fedora Linux"
        assert get_product_version() == "41"
        assert get_product_short_name() == "fedora"
