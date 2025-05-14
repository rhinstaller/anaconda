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

import unittest
from textwrap import dedent
from unittest.mock import mock_open, patch

import pyanaconda.core.product  # needed for patching, see below
from pyanaconda.core.product import (
    ProductData,
    get_product_is_final_release,
    get_product_name,
    get_product_short_name,
    get_product_values,
    get_product_version,
    shorten_product_name,
    trim_product_version_for_ui,
)


def make_buildstamp(product="Fedora", version="Rawhide", is_final=False):
    BUILDSTAMP_TEMPLATE = dedent("""\
        [Main]
        Product={}
        Version={}
        BugURL=your distribution provided bug reporting tool
        IsFinal={}
        UUID=197001010000.x86_64
        Variant=Everything
        [Compose]
        Lorax=39.2-1
    """)
    return BUILDSTAMP_TEMPLATE.format(
        product,
        version,
        is_final,
    )


def mock_multi_open(mock_file_data):
    """An extension of mock_open which supports repeated calls.

    This is needed, because when mocking builtins.open():
    - for multiple calls, it is possible to use the usual Mock with side_effect=[StringIO(), ...]
    - for use as a context manager, patch with new_callable=unittest.mock.mock_open
    However, neither of these works for the other case, so for... with open()... needs this.

    It is possible to cobble this together inline, too, but it's incredibly ugly and cryptic.
    """
    mo = mock_open()
    mo.side_effect = [
        mock_open(read_data=data).return_value for data in mock_file_data
    ]
    return mo


class ProductHelperTestCase(unittest.TestCase):

    def test_trim_product_version_for_ui(self):
        """Test version shortening."""
        trimmed_versions = [
            ("8.0.0", "8.0"),
            ("rawhide", "rawhide"),
            ("development", "rawhide"),
            ("7.6", "7.6"),
            ("7", "7"),
            ("8.0.0.1", "8.0"),
        ]

        for original, trimmed in trimmed_versions:
            assert trimmed == trim_product_version_for_ui(original)

    def test_short_product_name(self):
        """Test shortening product names."""
        assert shorten_product_name("UPPERCASE") == "uppercase"
        assert shorten_product_name("lowercase") == "lowercase"
        assert shorten_product_name("CamelCase") == "camelcase"
        assert shorten_product_name("Name With Spaces") == "nws"
        assert shorten_product_name("lowercase spaces") == "ls"
        assert shorten_product_name("something-WITH-dashes") == "something-with-dashes"
        assert shorten_product_name("Fedora") == "fedora"
        assert shorten_product_name("Red Hat Enterprise Linux") == "rhel"


class ProductTestCase(unittest.TestCase):
    """Test product value loading"""

    def setUp(self):
        # can't have the cache returning the same thing across all tests
        get_product_values.cache_clear()

    @classmethod
    def tearDownClass(cls):
        # invalidate cache also for all tests run after this
        get_product_values.cache_clear()

    @patch.dict("os.environ", clear=True)
    @patch.object(pyanaconda.core.product.configparser.ConfigParser, "read")
    def test_defaults(self, mock_cfp_read):
        """Test product value defaults."""
        values = get_product_values()
        expected = ProductData(False, "anaconda", "bluesky", "anaconda")

        assert values == expected
        mock_cfp_read.assert_called_once_with(["/.buildstamp", ""])

    @patch.dict("os.environ", clear=True)
    @patch("pyanaconda.core.product.configparser.open", new_callable=mock_multi_open,
           mock_file_data=[make_buildstamp("Fedora", "Rawhide", False), ""])
    def test_buildstamp(self, mock_cfp_open):
        """Test product values read from a buildstamp file."""
        values = get_product_values()
        expected = ProductData(False, "Fedora", "Rawhide", "fedora")

        assert values == expected
        mock_cfp_open.assert_called()

    @patch.dict("os.environ", clear=True, values={"PRODBUILDPATH": "/testing/file"})
    @patch("pyanaconda.core.product.configparser.open", new_callable=mock_multi_open,
           mock_file_data=[
               make_buildstamp("Fedora", "Rawhide", False),
               make_buildstamp("The Unfakeable Linux", "12.5.38.65536", False)
           ])
    def test_buildstamp_multiple(self, mock_cfp_open):
        """Test product values read from multiple buildstamp files."""
        values = get_product_values()
        expected = ProductData(False, "The Unfakeable Linux", "12.5", "tul")

        assert values == expected
        assert mock_cfp_open.call_count == 2

    @patch.dict("os.environ", clear=True, values={
        "ANACONDA_ISFINAL": "True",
        "ANACONDA_PRODUCTNAME": "TestProduct",
        "ANACONDA_PRODUCTVERSION": "development"
    })
    @patch("pyanaconda.core.product.configparser.open", side_effect=FileNotFoundError)
    def test_env(self, mock_cfp_open):
        """Test product values loaded from environment variables."""
        values = get_product_values()
        expected = ProductData(True, "TestProduct", "rawhide", "testproduct")
        assert values == expected

        # cached values are kept within single test fixture
        assert get_product_is_final_release() is True
        assert get_product_name() == "TestProduct"
        assert get_product_version() == "rawhide"
        assert get_product_short_name() == "testproduct"

        # caching means ConfigParser.read() calls open() twice, and subsequent calls are cached
        assert mock_cfp_open.call_count == 2
