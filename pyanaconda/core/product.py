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
from collections import namedtuple
from functools import cache

ProductData = namedtuple("ProductData", [
    "is_final_release",
    "name",
    "version",
    "short_name",
])


def get_os_release_value(name, sysroot="/"):
    """Read os-release files and return a value of the specified parameter.

    :param name: a name of the parameter (for example, "VERSION_ID")
    :param sysroot: a path to the system root
    :return: a string with the value of None if nothing found
    """
    # Match the variable assignment (for example, "VERSION_ID=").
    name += "="

    # Search all os-release files in the system root.
    paths = ("/etc/os-release", "/usr/lib/os-release")

    for path in paths:
        try:
            # Use os.path.join with path stripping to avoid circular import
            full_path = os.path.join(sysroot, path.lstrip("/"))
            with open(full_path, "r") as f:
                for line in f:
                    # Match the current line.
                    if not line.startswith(name):
                        continue

                    # Get the value.
                    value = line[len(name):]

                    # Strip spaces and then quotes.
                    value = value.strip().strip("\"'")
                    return value
        except FileNotFoundError:
            pass

    # No value found - avoid importing logger to prevent circular import
    return None


def trim_product_version_for_ui(version):
    """Trim off parts of version that should not be displayed in UI.

    Example: 8.0.1 -> 8.0

    :param str version: Version as read from the system
    :return str: Shortened version
    """
    if version.count('.') >= 2:
        version = '.'.join(version.split('.')[:2])

    return version

@cache
def get_product_values():
    """Provide product data based on /etc/os-release.

    :return: Data about product
    :rtype: ProductData
    """

    is_final_release = get_os_release_value("RELEASE_TYPE") != "development"
    product_name = get_os_release_value("NAME")
    product_version = trim_product_version_for_ui(get_os_release_value("VERSION_ID"))
    # for use in device names, eg: "fedora", "rhel"
    product_short_name = get_os_release_value("ID")

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
