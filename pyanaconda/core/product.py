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
from collections import namedtuple
from functools import cache

from pyanaconda.core.os_release import get_os_release_value

ProductData = namedtuple("ProductData", [
    "is_final_release",
    "name",
    "version",
    "short_name",
    "variant",
])


def trim_product_version_for_ui(version):
    """Trim off parts of version that should not be displayed in UI.

    Example: 8.0.1 -> 8.0

    :param str version: Version as read from the system
    :return str: Shortened version
    """
    if version.count('.') >= 2:
        version = '.'.join(version.split('.')[:2])

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
    """Provide product data from the installation environment's os-release.

    NAME, VERSION_ID and VARIANT provide the product name, version and variant.
    Missing or empty values default to "anaconda", "bluesky" and "", respectively.
    ID provides the short name, falling back to shortening the product name.

    The final release flag is read from RELEASE_TYPE in the installation
    environment's os-release files. Development and experimental releases are
    not final; other non-empty values are treated as stable. If RELEASE_TYPE
    is missing or empty, the release is not final.

    :return: Data about product
    :rtype: ProductData
    """

    release_type = get_os_release_value("RELEASE_TYPE")
    is_final_release = release_type not in (None, "", "development", "experiment")

    # Set up some variables we import throughout, applying a couple transforms as necessary.
    product_name = get_os_release_value("NAME") or "anaconda"
    product_version = trim_product_version_for_ui(get_os_release_value("VERSION_ID") or "bluesky")
    product_variant = get_os_release_value("VARIANT") or ""

    # for use in device names, eg: "fedora", "rhel"
    product_short_name = get_os_release_value("ID") or shorten_product_name(product_name)

    result = ProductData(
        is_final_release, product_name, product_version, product_short_name, product_variant
    )
    return result


def get_product_is_final_release():
    return get_product_values().is_final_release


def get_product_name():
    return get_product_values().name


def get_product_short_name():
    return get_product_values().short_name


def get_product_version():
    return get_product_values().version


def get_product_variant():
    return get_product_values().variant


def get_product_user_agent():
    """Build the installer User-Agent from product metadata."""
    product = get_product_values()
    return "{} (anaconda)/{}".format(product.name, product.version)
