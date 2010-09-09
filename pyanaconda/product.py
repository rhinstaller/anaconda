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

import ConfigParser
import os

# First, load in the defaults.  In order of precedence:  contents of
# .buildstamp, environment, stupid last ditch hardcoded defaults.
config = ConfigParser.ConfigParser({"Arch": os.environ.get("ANACONDA_PRODUCTARCH", ""),
                                    "BugURL": os.environ.get("ANACONDA_BUGURL", "your distribution provided bug reporting tool"),
                                    "IsBeta": os.environ.get("ANACONDA_ISBETA", "true").lower() == "true",
                                    "Product": os.environ.get("ANACONDA_PRODUCTNAME", "anaconda"),
                                    "UUID": "",
                                    "Version": os.environ.get("ANACONDA_PRODUCTVERSION", "bluesky")}
                                  )

# Now read in the .buildstamp file, wherever it may be.
config.read(["/tmp/product/.buildstamp", "/.buildstamp", os.environ.get("PRODBUILDPATH", "")])

# Set up some variables we import throughout, applying a couple transforms as necessary.
bugUrl = config.get("Main", "BugURL")
isBeta = config.get("Main", "IsBeta").lower() != "false"
productArch = config.get("Main", "Arch")
productName = config.get("Main", "Product")
productStamp = config.get("Main", "UUID")
productVersion = config.get("Main", "Version")

if not productArch:
    productArch = productStamp[productStamp.index(".")+1:]
if productVersion == "development":
    productVersion = "rawhide"
