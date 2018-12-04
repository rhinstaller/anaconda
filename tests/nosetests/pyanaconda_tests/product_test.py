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
# Red Hat Author(s): Vendula Poncova <vponcova@redhat.com>
#
import os
import tempfile
import unittest
from textwrap import dedent

from pyanaconda.core.configuration.anaconda import AnacondaConfiguration
from pyanaconda.core.configuration.base import ConfigurationError
from pyanaconda.core.configuration.product import ProductLoader

PRODUCT_DIR = os.path.join(os.environ.get("ANACONDA_DATA"), "product.d")


class ProductConfigurationTestCase(unittest.TestCase):
    """Test the default product configurations."""

    def setUp(self):
        """Set up the default loader."""
        self._loader = ProductLoader()
        self._loader.load_products(PRODUCT_DIR)

    def _load_product(self, content):
        """Load a product configuration with the given content."""
        with tempfile.NamedTemporaryFile("w") as f:
            f.write(content)
            f.flush()

            self._loader.load_product(f.name)
            return f.name

    def _check_product(self, product_name, variant_name, file_paths):
        """Check a product."""
        self.assertTrue(self._loader.check_product(product_name, variant_name))

        config_paths = self._loader.collect_configurations(product_name, variant_name)
        self.assertEqual(file_paths, config_paths)

    def _check_default_product(self, product_name, variant_name, file_names):
        """Check a default product."""
        self._check_product(
            product_name, variant_name,
            [os.path.join(PRODUCT_DIR, path) for path in file_names]
        )

        config = AnacondaConfiguration.from_defaults()
        paths = self._loader.collect_configurations(product_name, variant_name)

        for path in paths:
            config.read(path)

        config.validate()

    def fedora_products_test(self):
        self._check_default_product(
            "Fedora", "",
            ["fedora.conf"]
        )
        self._check_default_product(
            "Fedora", "Server",
            ["fedora.conf", "fedora-server.conf"]
        )
        self._check_default_product(
            "Fedora", "Workstation",
            ["fedora.conf", "fedora-workstation.conf"]
        )
        self._check_default_product(
            "Fedora", "Atomic Host",
            ["fedora.conf", "fedora-atomic-host.conf"]

        )
        self._check_default_product(
            "Fedora", "Silverblue",
            ["fedora.conf", "fedora-workstation.conf", "fedora-silverblue.conf"]
        )

    def rhel_products_test(self):
        self._check_default_product(
            "Red Hat Enterprise Linux", "",
            ["rhel.conf"]
        )
        self._check_default_product(
            "CentOS Linux", "",
            ["rhel.conf", "centos.conf"]
        )
        self._check_default_product(
            "Scientific Linux", "",
            ["rhel.conf", "scientific-linux.conf"]
        )

    def valid_product_test(self):
        content = dedent("""
        [Product]
        product_name = My Product
        """)

        base_path = self._load_product(content)
        self._check_product("My Product", "", [base_path])

        content = dedent("""
        [Product]
        product_name = My Next Product

        [Base Product]
        product_name = My Product
        """)

        path = self._load_product(content)
        self._check_product("My Next Product", "", [base_path, path])

    def valid_variant_test(self):
        content = dedent("""
        [Product]
        product_name = My Product
        variant_name = My Variant
        """)

        base_path = self._load_product(content)
        self._check_product("My Product", "My Variant", [base_path])

        content = dedent("""
        [Product]
        product_name = My Product
        variant_name = My Next Variant

        [Base Product]
        product_name = My Product
        variant_name = My Variant
        """)

        path = self._load_product(content)
        self._check_product("My Product", "My Next Variant", [base_path, path])

    def invalid_product_test(self):
        with self.assertRaises(ConfigurationError):
            self._load_product("")

        with self.assertRaises(ConfigurationError):
            self._load_product("[Product]")

        with self.assertRaises(ConfigurationError):
            self._load_product("[Base Product]")

        content = dedent("""
        [Product]
        variant_name = Server

        """)

        with self.assertRaises(ConfigurationError):
            self._load_product(content)

        content = dedent("""
        [Base Product]
        product_name = My Product

        """)

        with self.assertRaises(ConfigurationError):
            self._load_product(content)

    def invalid_base_product_test(self):
        content = dedent("""
        [Product]
        product_name = My Product

        [Base Product]
        product_name = Nonexistent Product
        """)
        self._load_product(content)

        with self.assertRaises(ConfigurationError):
            self._loader.collect_configurations("My Product")

        self.assertFalse(self._loader.check_product("My Product"))

    def repeated_base_product_test(self):
        content = dedent("""
        [Product]
        product_name = My Product

        [Base Product]
        product_name = My Product
        """)
        self._load_product(content)

        with self.assertRaises(ConfigurationError):
            self._loader.collect_configurations("My Product")

        self.assertFalse(self._loader.check_product("My Product"))

    def existing_product_test(self):
        content = dedent("""
        [Product]
        product_name = My Product
        """)

        self._load_product(content)

        with self.assertRaises(ConfigurationError):
            self._load_product(content)

    def find_nonexistent_product_test(self):
        self._loader.check_product("Nonexistent Product")
        self._loader.check_product("Nonexistent Product", "Nonexistent Variant")

    def ignore_invalid_product_test(self):
        with tempfile.TemporaryDirectory() as config_dir:

            # A correct product config.
            with open(os.path.join(config_dir, "1.conf"), "w") as f:
                f.write(dedent("""
                [Product]
                product_name = My Product 1
                """))

            # An invalid product config.
            with open(os.path.join(config_dir, "2.conf"), "w") as f:
                f.write("")

            # A product config with wrong file name.
            with open(os.path.join(config_dir, "3"), "w") as f:
                f.write(dedent("""
                [Product]
                product_name = My Product 3
                """))

            self._loader.load_products(config_dir)
            self.assertTrue(self._loader.check_product("My Product 1"))
            self.assertFalse(self._loader.check_product("My Product 2"))
            self.assertFalse(self._loader.check_product("My Product 3"))
