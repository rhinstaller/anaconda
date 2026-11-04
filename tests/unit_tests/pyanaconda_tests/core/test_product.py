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
# Test product metadata loading.
#

import unittest
from unittest.mock import mock_open, patch

from pyanaconda.core.os_release import get_os_release_value
from pyanaconda.core.product import (
    ProductData,
    get_product_is_final_release,
    get_product_name,
    get_product_short_name,
    get_product_user_agent,
    get_product_values,
    get_product_variant,
    get_product_version,
    shorten_product_name,
    trim_product_version_for_ui,
)


class ProductHelperTestCase(unittest.TestCase):

    def test_trim_product_version_for_ui(self):
        """Test version shortening."""
        trimmed_versions = [
            ("8.0.0", "8.0"),
            ("rawhide", "rawhide"),
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
        self.addCleanup(get_product_values.cache_clear)
        self.metadata = {}
        self.os_release = self.enterContext(patch(
            "pyanaconda.core.product.get_os_release_value", side_effect=self.metadata.get
        ))

    def test_defaults(self):
        """Missing and empty metadata use product defaults."""
        for value in (None, ""):
            with self.subTest(value=value):
                get_product_values.cache_clear()
                self.metadata.update(dict.fromkeys(
                    ("NAME", "VERSION_ID", "RELEASE_TYPE", "VARIANT"), value
                ))
                assert get_product_values() == ProductData(
                    False, "anaconda", "bluesky", "anaconda", ""
                )

    def test_product_metadata(self):
        """Read product metadata, trim the version and cache the result."""
        self.metadata.update({
            "NAME": "The Unfakeable Linux",
            "VERSION_ID": "12.5.38.65536",
            "RELEASE_TYPE": "stable",
            "VARIANT": "Everything",
            "BUILD_ID": "devel",
        })
        assert get_product_values() == ProductData(
            True, "The Unfakeable Linux", "12.5", "tul", "Everything"
        )
        self.metadata.clear()
        assert get_product_is_final_release() is True
        assert get_product_name() == "The Unfakeable Linux"
        assert get_product_version() == "12.5"
        assert get_product_short_name() == "tul"
        assert get_product_variant() == "Everything"
        assert get_product_user_agent() == "The Unfakeable Linux (anaconda)/12.5"
        assert self.os_release.call_count == 5

    @patch.dict("os.environ", clear=True, values={
        "ANACONDA_ISFINAL": "True",
        "ANACONDA_PRODUCTNAME": "TestProduct",
        "ANACONDA_PRODUCTVERSION": "rawhide",
        "PRODBUILDPATH": "/testing/file",
    })
    @patch("builtins.open", side_effect=AssertionError("Unexpected metadata file read"))
    def test_ignores_legacy_sources(self, open_mock):
        """Neither environment overrides nor buildstamp files provide metadata."""
        for metadata, expected in (
            ({}, ProductData(False, "anaconda", "bluesky", "anaconda", "")),
            ({"NAME": "Fedora", "VERSION_ID": "46", "RELEASE_TYPE": "development",
              "VARIANT": "Everything"},
             ProductData(False, "Fedora", "46", "fedora", "Everything")),
        ):
            with self.subTest(metadata=metadata):
                get_product_values.cache_clear()
                self.metadata.update(metadata)
                assert get_product_values() == expected
        open_mock.assert_not_called()

    def test_release_type(self):
        """Only RELEASE_TYPE determines final status."""
        for release_type, expected in (
            ("stable", True),
            ("lts", True),
            ("development", False),
            ("experiment", False),
            ("unknown", True),
            (None, False),
            ("", False),
        ):
            with self.subTest(release_type=release_type):
                get_product_values.cache_clear()
                self.metadata["RELEASE_TYPE"] = release_type
                assert get_product_is_final_release() is expected

    def test_os_release_files(self):
        """Read the product through the real os-release reader."""
        with patch("pyanaconda.core.product.get_os_release_value",
                   new=get_os_release_value):
            with patch("pyanaconda.core.os_release.open", mock_open(read_data=(
                'NAME="Fedora Linux"\nID=fedora\nVERSION_ID=46\nRELEASE_TYPE=development\n'
                'VARIANT="Everything"\nBUILD_ID=devel\n'
            ))) as open_mock:
                assert get_product_values() == ProductData(
                    False, "Fedora Linux", "46", "fedora", "Everything"
                )
                assert all(call.args[0] == "/etc/os-release" for call in open_mock.call_args_list)
