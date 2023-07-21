#
# product.py: product identification string
#
# Copyright (C) 2003  Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import configparser
import os

from pyanaconda.core.i18n import _

__all__ = ["isFinal", "productName", "productVersion", "shortProductName", "distributionText"]

# Order of precedence for the variables published in __all__ is:
#   1) Buildstamp file specified by the PRODBUILDPATH environment variable
#   2) Buildstamp file /.buildstamp
#   3) Environment variable ANACONDA_ISFINAL
#   4) In absence of any data, fall back to "false"


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
isFinal = config.getboolean("Main", "IsFinal")
productName = config.get("Main", "Product")
productVersion = config.get("Main", "Version")

if productVersion == "development":
    productVersion = "rawhide"

# for use in device names, eg: "fedora", "rhel"
shortProductName = productName.lower()          # pylint: disable=no-member
if productName.count(" "):                      # pylint: disable=no-member
    shortProductName = ''.join(s[0] for s in shortProductName.split())


def trim_product_version_for_ui(version):
    """Trim off parts of version that should not be displayed in UI.

    Example: 8.0.1 -> 8.0
    """
    if version.count('.') >= 2:
        version = '.'.join(version.split('.')[:2])
    return version


productVersion = trim_product_version_for_ui(productVersion)


def distributionText():
    return _("%(productName)s %(productVersion)s INSTALLATION") % {
        "productName": productName.upper(),
        "productVersion": productVersion.upper()
    }
