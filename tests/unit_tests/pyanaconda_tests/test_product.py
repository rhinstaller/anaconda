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

import pytest
from blivet.size import Size

from pyanaconda.core.configuration.anaconda import AnacondaConfiguration
from pyanaconda.core.configuration.base import (
    ConfigurationError,
    create_parser,
    read_config,
)
from pyanaconda.core.configuration.product import ProductLoader
from pyanaconda.modules.storage.partitioning.automatic.utils import (
    get_default_partitioning,
)
from pyanaconda.modules.storage.partitioning.specification import PartSpec
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
        encrypted=True,
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
        encrypted=True,
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
]

ENTERPRISE_PARTITIONING = [
    PartSpec(
        mountpoint="/",
        size=Size("1GiB"),
        max_size=Size("70GiB"),
        grow=True,
        btr=True,
        lv=True,
        thin=True,
        encrypted=True,
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
    ),
]

VIRTUALIZATION_PARTITIONING = [
    PartSpec(
        mountpoint="/",
        size=Size("6GiB"),
        grow=True,
        btr=True,
        lv=True,
        thin=True,
        encrypted=True,
    ),
    PartSpec(
        mountpoint="/home",
        size=Size("1GiB"),
        btr=True,
        lv=True,
        thin=True,
        encrypted=True,
    ),
    PartSpec(
        mountpoint="/tmp",
        size=Size("1GiB"),
        btr=True,
        lv=True,
        thin=True,
        encrypted=True,
    ),
    PartSpec(
        mountpoint="/var",
        size=Size("5GiB"),
        btr=True,
        lv=True,
        thin=True,
        encrypted=True,
    ),
    PartSpec(
        mountpoint="/var/crash",
        size=Size("10GiB"),
        btr=True,
        lv=True,
        thin=True,
        encrypted=True,
    ),
    PartSpec(
        mountpoint="/var/log",
        size=Size("8GiB"),
        btr=True,
        lv=True,
        thin=True,
        encrypted=True,
    ),
    PartSpec(
        mountpoint="/var/log/audit",
        size=Size("2GiB"),
        btr=True,
        lv=True,
        thin=True,
        encrypted=True,
    ),
    PartSpec(
        mountpoint="/var/tmp",
        size=Size("10GiB"),
        btr=True,
        lv=True,
        thin=True,
        encrypted=True,
    ),
    PartSpec(
        fstype="swap",
        lv=True,
        encrypted=True,
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
        assert self._loader.check_product(product_name, variant_name) is True

        config_paths = self._loader.collect_configurations(product_name, variant_name)
        assert file_paths == config_paths

    def _check_partitioning(self, config, partitioning):
        with patch("pyanaconda.modules.storage.partitioning.automatic.utils.platform") as platform:
            platform.partitions = []

            with patch("pyanaconda.modules.storage.partitioning.automatic.utils.conf", new=config):
                assert get_default_partitioning() == partitioning

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

    def test_fedora_products(self):
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
            "Fedora", "Silverblue",
            ["fedora.conf", "fedora-workstation.conf", "fedora-workstation-live.conf",
             "fedora-silverblue.conf"],
            WORKSTATION_PARTITIONING
        )
        self._check_default_product(
            "Fedora-IoT", "IoT",
            ["fedora.conf", "fedora-iot.conf"],
            WORKSTATION_PARTITIONING
        )
        self._check_default_product(
            "Fedora-ELN", "",
            ["rhel.conf", "fedora-eln.conf"],
            ENTERPRISE_PARTITIONING
        )

    def test_rhel_products(self):
        self._check_default_product(
            "Red Hat Enterprise Linux", "",
            ["rhel.conf"],
            ENTERPRISE_PARTITIONING
        )
        self._check_default_product(
            "CentOS Stream", "",
            ["rhel.conf", "centos-stream.conf"],
            ENTERPRISE_PARTITIONING
        )
        self._check_default_product(
            "CentOS Linux", "",
            ["rhel.conf", "centos-stream.conf", "centos.conf"],
            ENTERPRISE_PARTITIONING
        )
        self._check_default_product(
            "RHVH", "",
            ["rhel.conf", "rhvh.conf"],
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
            ENTERPRISE_PARTITIONING
        )
        self._check_default_product(
            "AlmaLinux", "",
            ["rhel.conf", "almalinux.conf"],
            ENTERPRISE_PARTITIONING
        )
        self._check_default_product(
            "Rocky Linux", "",
            ["rhel.conf", "rocky.conf"],
            ENTERPRISE_PARTITIONING
        )
        self._check_default_product(
            "Virtuozzo Linux", "",
            ["rhel.conf", "virtuozzo-linux.conf"],
            ENTERPRISE_PARTITIONING
        )
        self._check_default_product(
            "Circle Linux", "",
            ["rhel.conf", "circle.conf"],
            ENTERPRISE_PARTITIONING
        )

    def _compare_product_files(self, file_name, other_file_name):
        parser = create_parser()
        read_config(parser, os.path.join(PRODUCT_DIR, file_name))

        other_parser = create_parser()
        read_config(other_parser, os.path.join(PRODUCT_DIR, other_file_name))

        # The defined sections should be the same.
        assert parser.sections() == other_parser.sections()

        for section in parser.sections():
            # Skip the product-related sections.
            if section in ("Product", "Base Product"):
                continue

            # The defined options should be the same.
            assert parser.options(section) == other_parser.options(section)

            for key in parser.options(section):
                # The values of the options should be the same.
                assert parser.get(section, key) == other_parser.get(section, key)

    def test_ovirt_and_rhvh(self):
        """Test the similarity of oVirt Node Next with Red Hat Virtualization Host."""
        self._compare_product_files("rhvh.conf", "ovirt.conf")

    def test_valid_product(self):
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

    def test_valid_variant(self):
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

    def test_invalid_product(self):
        with pytest.raises(ConfigurationError):
            self._load_product("")

        with pytest.raises(ConfigurationError):
            self._load_product("[Product]")

        with pytest.raises(ConfigurationError):
            self._load_product("[Base Product]")

        content = dedent("""
        [Product]
        variant_name = Server

        """)

        with pytest.raises(ConfigurationError):
            self._load_product(content)

        content = dedent("""
        [Base Product]
        product_name = My Product

        """)

        with pytest.raises(ConfigurationError):
            self._load_product(content)

    def test_invalid_base_product(self):
        content = dedent("""
        [Product]
        product_name = My Product

        [Base Product]
        product_name = Nonexistent Product
        """)
        self._load_product(content)

        with pytest.raises(ConfigurationError):
            self._loader.collect_configurations("My Product")

        assert self._loader.check_product("My Product") is False

    def test_repeated_base_product(self):
        content = dedent("""
        [Product]
        product_name = My Product

        [Base Product]
        product_name = My Product
        """)
        self._load_product(content)

        with pytest.raises(ConfigurationError):
            self._loader.collect_configurations("My Product")

        assert self._loader.check_product("My Product") is False

    def test_existing_product(self):
        content = dedent("""
        [Product]
        product_name = My Product
        """)

        self._load_product(content)

        with pytest.raises(ConfigurationError):
            self._load_product(content)

    def test_find_nonexistent_product(self):
        self._loader.check_product("Nonexistent Product")
        self._loader.check_product("Nonexistent Product", "Nonexistent Variant")

    def test_ignore_invalid_product(self):
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
            assert self._loader.check_product("My Product 1") is True
            assert self._loader.check_product("My Product 2") is False
            assert self._loader.check_product("My Product 3") is False


class ProductFromBuildstampTests(unittest.TestCase):

    def test_trim_product_version_for_ui(self):
        trimmed_versions = [
            ("8.0.0", "8.0"),
            ("rawhide", "rawhide"),
            ("7.6", "7.6"),
            ("7", "7"),
            ("8.0.0.1", "8.0"),
        ]

        for original, trimmed in trimmed_versions:
            assert trimmed == trim_product_version_for_ui(original)
