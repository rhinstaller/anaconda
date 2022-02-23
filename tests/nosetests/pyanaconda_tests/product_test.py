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
from unittest.mock import patch

from blivet.size import Size

from pyanaconda.modules.storage.partitioning.automatic.utils import get_default_partitioning
from pyanaconda.modules.storage.partitioning.specification import PartSpec

from pyanaconda.core.configuration.anaconda import AnacondaConfiguration
from pyanaconda.core.configuration.base import ConfigurationError, create_parser, read_config
from pyanaconda.core.configuration.product import ProductLoader
from pyanaconda.product import trim_product_version_for_ui

PRODUCT_DIR = os.path.join(os.environ.get("ANACONDA_DATA"), "product.d")

SERVER_PARTITIONING = [
    PartSpec(
        mountpoint="/",
        size=Size("2GiB"),
        max_size=Size("15GiB"),
        grow=True,
        btr=True,
        lv=True,
        thin=True,
        encrypted=True
    ),
    PartSpec(
        fstype="swap",
        lv=True,
        encrypted=True
    )
]

WORKSTATION_PARTITIONING = [
    PartSpec(
        mountpoint="/",
        size=Size("1GiB"),
        max_size=Size("70GiB"),
        grow=True,
        btr=True,
        lv=True,
        thin=True,
        encrypted=True
    ),
    PartSpec(
        mountpoint="/home",
        size=Size("500MiB"), grow=True,
        required_space=Size("50GiB"),
        btr=True,
        lv=True,
        thin=True,
        encrypted=True
    ),
    PartSpec(
        fstype="swap",
        lv=True,
        encrypted=True
    )
]

VIRTUALIZATION_PARTITIONING = [
    PartSpec(
        mountpoint="/",
        size=Size("6GiB"),
        grow=True,
        btr=True,
        lv=True,
        thin=True,
        encrypted=True
    ),
    PartSpec(
        mountpoint="/home",
        size=Size("1GiB"),
        btr=True,
        lv=True,
        thin=True,
        encrypted=True
    ),
    PartSpec(
        mountpoint="/tmp",
        size=Size("1GiB"),
        btr=True,
        lv=True,
        thin=True,
        encrypted=True
    ),
    PartSpec(
        mountpoint="/var",
        size=Size("5GiB"),
        btr=True,
        lv=True,
        thin=True,
        encrypted=True
    ),
    PartSpec(
        mountpoint="/var/crash",
        size=Size("10GiB"),
        btr=True,
        lv=True,
        thin=True,
        encrypted=True
    ),
    PartSpec(
        mountpoint="/var/log",
        size=Size("8GiB"),
        btr=True,
        lv=True,
        thin=True,
        encrypted=True
    ),
    PartSpec(
        mountpoint="/var/log/audit",
        size=Size("2GiB"),
        btr=True,
        lv=True,
        thin=True,
        encrypted=True
    ),
    PartSpec(
        mountpoint="/var/tmp",
        size=Size("10GiB"),
        btr=True,
        lv=True,
        thin=True,
        encrypted=True
    ),
    PartSpec(
        fstype="swap",
        lv=True,
        encrypted=True
    )
]


class ProductConfigurationTestCase(unittest.TestCase):
    """Test the default product configurations."""

    def setUp(self):
        """Set up the default loader."""
        self.maxDiff = None
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

    def _check_partitioning(self, config, partitioning):
        with patch("pyanaconda.modules.storage.partitioning.automatic.utils.platform") as platform:
            platform.set_default_partitioning.return_value = []

            with patch("pyanaconda.modules.storage.partitioning.automatic.utils.conf", new=config):
                self.assertEqual(get_default_partitioning(), partitioning)

    def _check_default_product(self, product_name, variant_name, file_names, partitioning):
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

        self._check_partitioning(config, partitioning)

    def _get_config(self, product_name, variant_name=""):
        """Get parsed config file."""
        config = AnacondaConfiguration.from_defaults()
        paths = self._loader.collect_configurations(product_name, variant_name)

        for path in paths:
            config.read(path)

        config.validate()

        return config

    def fedora_products_test(self):
        self._check_default_product(
            "Fedora", "",
            ["fedora.conf"],
            WORKSTATION_PARTITIONING
        )
        self._check_default_product(
            "Fedora", "Server",
            ["fedora.conf", "fedora-server.conf"],
            SERVER_PARTITIONING
        )
        self._check_default_product(
            "Fedora", "Workstation",
            ["fedora.conf", "fedora-workstation.conf"],
            WORKSTATION_PARTITIONING
        )
        self._check_default_product(
            "Fedora", "Workstation Live",
            ["fedora.conf", "fedora-workstation.conf", "fedora-workstation-live.conf"],
            WORKSTATION_PARTITIONING
        )
        self._check_default_product(
            "Fedora", "AtomicHost",
            ["fedora.conf", "fedora-atomic-host.conf"],
            SERVER_PARTITIONING

        )
        self._check_default_product(
            "Fedora", "Silverblue",
            ["fedora.conf", "fedora-workstation.conf", "fedora-workstation-live.conf",
             "fedora-silverblue.conf"],
            WORKSTATION_PARTITIONING
        )

    def rhel_products_test(self):
        self._check_default_product(
            "Red Hat Enterprise Linux", "",
            ["rhel.conf"],
            WORKSTATION_PARTITIONING
        )
        self._check_default_product(
            "CentOS Stream", "",
            ["rhel.conf", "centos-stream.conf"],
            WORKSTATION_PARTITIONING
        )
        self._check_default_product(
            "CentOS Linux", "",
            ["rhel.conf", "centos-stream.conf", "centos.conf"],
            WORKSTATION_PARTITIONING
        )
        self._check_default_product(
            "Red Hat Virtualization", "",
            ["rhel.conf", "rhev.conf"],
            VIRTUALIZATION_PARTITIONING
        )
        self._check_default_product(
            "oVirt Node Next", "",
            ["rhel.conf", "centos-stream.conf", "ovirt.conf"],
            VIRTUALIZATION_PARTITIONING
        )
        self._check_default_product(
            "Scientific Linux", "",
            ["rhel.conf", "scientific-linux.conf"],
            WORKSTATION_PARTITIONING
        )
        self._check_default_product(
            "AlmaLinux", "",
            ["rhel.conf", "almalinux.conf"],
            WORKSTATION_PARTITIONING
        )

    def product_module_list_difference_fedora_rhel_test(self):
        """Test for expected Fedora & RHEL module list differences."""
        fedora_config = self._get_config("Fedora")
        fedora_modules = fedora_config.anaconda.kickstart_modules

        rhel_config = self._get_config("Red Hat Enterprise Linux")
        rhel_modules = rhel_config.anaconda.kickstart_modules

        difference = list(set(rhel_modules) - set(fedora_modules))
        expected_difference = ["org.fedoraproject.Anaconda.Modules.Subscription"]

        self.assertListEqual(difference, expected_difference)

    def product_module_difference_centos_rhel_test(self):
        """Test for expected CentOS & RHEL module list differences."""
        centos_config = self._get_config("CentOS Linux")
        centos_modules = centos_config.anaconda.kickstart_modules

        rhel_config = self._get_config("Red Hat Enterprise Linux")
        rhel_modules = rhel_config.anaconda.kickstart_modules

        difference = list(set(rhel_modules) - set(centos_modules))
        expected_difference = ["org.fedoraproject.Anaconda.Modules.Subscription"]

        self.assertListEqual(difference, expected_difference)

    def _compare_product_files(self, file_name, other_file_name):
        parser = create_parser()
        read_config(parser, os.path.join(PRODUCT_DIR, file_name))

        other_parser = create_parser()
        read_config(other_parser, os.path.join(PRODUCT_DIR, other_file_name))

        # The defined sections should be the same.
        self.assertEqual(parser.sections(), other_parser.sections())

        for section in parser.sections():
            # Skip the product-related sections.
            if section in ("Product", "Base Product"):
                continue

            # The defined options should be the same.
            self.assertEqual(parser.options(section), other_parser.options(section))

            for key in parser.options(section):
                # The values of the options should be the same.
                self.assertEqual(parser.get(section, key), other_parser.get(section, key))

    def ovirt_and_rhev_test(self):
        """Test the similarity of oVirt Node Next with Red Hat Virtualization."""
        self._compare_product_files("rhev.conf", "ovirt.conf")

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


class ProductFromBuildstampTests(unittest.TestCase):

    def trim_product_version_for_ui_test(self):
        trimmed_versions = [
            ("8.0.0", "8.0"),
            ("rawhide", "rawhide"),
            ("7.6", "7.6"),
            ("7", "7"),
            ("8.0.0.1", "8.0"),
        ]

        for original, trimmed in trimmed_versions:
            self.assertEqual(trimmed, trim_product_version_for_ui(original))
