#
# Copyright (C) 2018 Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
#  Author(s):  Vendula Poncova <vponcova@redhat.com>
#
import os
from collections import namedtuple

from pyanaconda.core.configuration.base import create_parser, read_config, get_option, \
    ConfigurationError

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


__all__ = ["ProductLoader"]


ProductKey = namedtuple("Product", ["product_name", "variant_name"])
ProductKey.__doc__ = "Identification of the product."
ProductKey.__str__ = lambda key: " ".join(filter(None, key))


ProductData = namedtuple("ProductData", ["base_product", "config_path"])
ProductData.__doc__ = "Data of the product."


class ProductLoader(object):
    """A class for loading information about products from configuration files."""

    def __init__(self):
        """Create a new loader."""
        self._products = {}

    def load_products(self, config_dir):
        """Load information about products from the given configuration directory.

        Invalid configuration files will be skipped.

        :param config_dir: a path to a directory
        """
        log.info("Loading information about products from %s.", config_dir)

        for file_name in os.listdir(config_dir):
            if not file_name.endswith(".conf"):
                continue

            config_path = os.path.join(config_dir, file_name)

            try:
                self.load_product(config_path)
            except ConfigurationError as e:
                log.error("Skipping an invalid configuration at %s: %s", config_path, e)

    def load_product(self, config_path):
        """Load information about a product from the given configuration file.

        :param config_path: a path to a configuration file
        :raises: ConfigurationError if a product cannot be loaded
        """
        # Set up the parser.
        parser = create_parser()
        self._create_section(parser, "Product")
        self._create_section(parser, "Base Product")

        # Read the product sections.
        read_config(parser, config_path)
        key = self._read_section(parser, "Product")
        base = self._read_section(parser, "Base Product")

        # Check the product.
        if not key.product_name:
            raise ConfigurationError("The product name is not specified.")

        if key in self._products:
            raise ConfigurationError("The product {} was already loaded.".format(key))

        # Check the base product.
        if not base.product_name:
            base = None

        # Add the product.
        log.info("Found %s at %s.", key, config_path)
        self._products[key] = ProductData(base, config_path)

    def check_product(self, product_name, variant_name=""):
        """Check if the specified product is supported.

        :param product_name: a name of the product
        :param variant_name: a name of the variant
        :return: True if the product is supported, otherwise False
        """
        product_key = ProductKey(product_name, variant_name)

        if product_key not in self._products:
            log.warning("No support for the product %s.", product_key)
            return False

        try:
            self._get_product_bases(product_key)
        except ConfigurationError as e:
            log.warning("Invalid support for the product %s: %s", product_key, e)
            return False

        log.info("The product %s is supported.", product_key)
        return True

    def collect_configurations(self, product_name, variant_name=""):
        """Collect configuration files of the given product.

        The configuration files should be processed in the given order.

        :param product_name: a name of the product
        :param variant_name: a name of the variant
        :return: a list of paths to configuration files
        """
        return self._get_product_configs(ProductKey(product_name, variant_name))

    def _create_section(self, parser, section_name):
        """Create the product section.

        :param parser: a configuration parser
        :param section_name: a name of a product section
        """
        parser.add_section(section_name)
        parser.set(section_name, "product_name", "")
        parser.set(section_name, "variant_name", "")

    def _read_section(self, parser, section_name):
        """Read the product section.

        :param parser: a configuration parser
        :param section_name: a name of a product section
        :return: a key of the product
        """
        product_name = get_option(parser, section_name, "product_name")
        variant_name = get_option(parser, section_name, "variant_name")
        return ProductKey(product_name, variant_name)

    def _get_product_config(self, product_key):
        """Get the configuration path of the product.

        :param product_key: a key of the product
        :return: a path to a configuration file
        """
        return self._products.get(product_key).config_path

    def _get_product_configs(self, product_key):
        """Get a list of configuration paths of the product.

        The configuration files should be processed in the given order.

        :param product_key: a key of the product
        :return: a list of paths to a configuration files
        """
        product_keys = reversed(self._get_product_bases(product_key))
        return [self._get_product_config(key) for key in product_keys]

    def _get_product_base(self, product_key):
        """Get the base of the product.

        :param product_key: a key of the product
        :return: a key of the base product
        """
        return self._products.get(product_key).base_product

    def _get_product_bases(self, product_key):
        """Return a list of bases of the given product.

        The products are ordered by the "is based on" relation.

        If the product A is based on the product B and the product B
        is based on the product C, then the related products of the
        product A are: A, B, C

        :param product_key: a key of the product
        :return: a list of keys of the base products
        :raises: ConfigurationError if the dependencies cannot be resolved
        """
        current_key = product_key
        visited = set()
        products = []

        while current_key:
            if current_key not in self._products:
                raise ConfigurationError(
                    "Dependencies of the product {} cannot be resolved "
                    "due to an unknown product {}.".format(product_key, current_key)
                )

            if current_key in visited:
                raise ConfigurationError(
                    "Dependencies of the product {} cannot be resolved "
                    "due to a conflict with {}.".format(product_key, current_key)
                )

            visited.add(current_key)
            products.append(current_key)
            current_key = self._get_product_base(current_key)

        return products
