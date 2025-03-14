#
# Copyright (C) 2023 Red Hat, Inc.
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
import configparser
import os
from collections import namedtuple
from functools import cache

ProductData = namedtuple("ProductData", [
    "is_final_release",
    "name",
    "version",
    "short_name",
])


def trim_product_version_for_ui(version):
    """Trim off parts of version that should not be displayed in UI.

    Example: 8.0.1 -> 8.0

    :param str version: Version as read from the system
    :return str: Shortened version
    """
    if version.count('.') >= 2:
        version = '.'.join(version.split('.')[:2])

    # Correctly report Rawhide
    if version == "development":
        version = "rawhide"

    return version


def shorten_product_name(long_name):
    """Shorten a product name.

    This is used in device names. eg. "fedora", "rhel".

    :param str long_name: Name of the product, as read from the system
    :return str: Short name for the product
    """
    product_short_name = long_name.lower()  # pylint: disable=no-member

    if long_name.count(" "):  # pylint: disable=no-member
        product_short_name = ''.join(s[0] for s in product_short_name.split())

    return product_short_name


@cache
def get_product_values():
    """Provide product data based on available inputs.

    Order of precedence for the values is:
      1) Buildstamp file specified by the PRODBUILDPATH environment variable
      2) Buildstamp file /.buildstamp
      3) Environment variable ANACONDA_ISFINAL
      4) In absence of any data, fall back to "false"

    :return: Data about product
    :rtype: ProductData
    """

    # First, load in the defaults.  In order of precedence:  contents of
    # .buildstamp, environment, stupid last ditch hardcoded defaults.
    config = configparser.ConfigParser()
    config.add_section("Main")
    config.set("Main", "IsFinal", os.environ.get("ANACONDA_ISFINAL", "false"))
    config.set("Main", "Product", os.environ.get("ANACONDA_PRODUCTNAME", "anaconda"))
    config.set("Main", "Version", os.environ.get("ANACONDA_PRODUCTVERSION", "bluesky"))

    # Now read in the .buildstamp file, wherever it may be.
    config.read(["/.buildstamp", os.environ.get("PRODBUILDPATH", "")])

    # Set up some variables we import throughout, applying a couple transforms as necessary.
    is_final_release = config.getboolean("Main", "IsFinal")
    product_name = config.get("Main", "Product")
    product_version = trim_product_version_for_ui(config.get("Main", "Version"))

    # for use in device names, eg: "fedora", "rhel"
    product_short_name = shorten_product_name(product_name)

    result = ProductData(is_final_release, product_name, product_version, product_short_name)
    return result


def get_product_is_final_release():
    return get_product_values().is_final_release


def get_product_name():
    return get_product_values().name


def get_product_short_name():
    return get_product_values().short_name


def get_product_version():
    return get_product_values().version
