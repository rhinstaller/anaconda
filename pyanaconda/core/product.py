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
import os
from functools import cache

from pyanaconda.modules.common.structures.product import ProductData


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
      3) ANACONDA_ISFINAL based on /etc/os-release RELEASE_TYPE field
      4) In absence of any data, fall back to "false"

    :return: Data about product
    :rtype: ProductData
    """

    product_data = ProductData()

    product_data.is_final_release = (util.get_os_release_value("RELEASE_TYPE") != "development")
    product_data.name = os.environ.get("ANACONDA_PRODUCTNAME", "anaconda")
    product_data.version = os.environ.get("ANACONDA_PRODUCTVERSION", "bluesky")
    product_data.short_name = shorten_product_name(product_data.name)

    return product_data


def get_product_is_final_release():
    return get_product_values().is_final_release


def get_product_name():
    return get_product_values().name


def get_product_short_name():
    return get_product_values().short_name


def get_product_version():
    return get_product_values().version
