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

from pyanaconda.i18n import _

# First, load in the defaults.  In order of precedence:  contents of
# .buildstamp, environment, stupid last ditch hardcoded defaults.
config = ConfigParser.ConfigParser()
config.add_section("Main")
config.set("Main", "Arch", os.environ.get("ANACONDA_PRODUCTARCH", os.uname()[4]))
config.set("Main", "BugURL", os.environ.get("ANACONDA_BUGURL", "your distribution provided bug reporting tool"))
config.set("Main", "IsFinal", os.environ.get("ANACONDA_ISFINAL", "false"))
config.set("Main", "Product", os.environ.get("ANACONDA_PRODUCTNAME", "anaconda"))
config.set("Main", "UUID", "")
config.set("Main", "Version", os.environ.get("ANACONDA_PRODUCTVERSION", "bluesky"))

# Now read in the .buildstamp file, wherever it may be.
config.read(["/tmp/product/.buildstamp", "/.buildstamp", os.environ.get("PRODBUILDPATH", "")])

# Set up some variables we import throughout, applying a couple transforms as necessary.
bugUrl = config.get("Main", "BugURL")
isFinal = config.getboolean("Main", "IsFinal")
productArch = config.get("Main", "Arch")
productName = config.get("Main", "Product")
productStamp = config.get("Main", "UUID")
productVersion = config.get("Main", "Version")

if not productArch and productStamp.index(".") != -1:
    productArch = productStamp[productStamp.index(".")+1:]
if productVersion == "development":
    productVersion = "rawhide"

def distributionText():
    return _("%(productName)s %(productVersion)s INSTALLATION") % \
             {"productName": productName, "productVersion": productVersion}

def translated_new_install_name():
    return _("New %(name)s %(version)s Installation") % \
        {"name" : productName, "version" : productVersion}
