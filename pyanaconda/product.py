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

import os

if os.access("/tmp/product/.buildstamp", os.R_OK):
    path = "/tmp/product/.buildstamp"
elif os.access("/.buildstamp", os.R_OK):
    path = "/.buildstamp"
elif os.environ.has_key("PRODBUILDPATH") and \
         os.access(os.environ["PRODBUILDPATH"], os.R_OK):
    path = os.environ["PRODBUILDPATH"]
else:
    path = None

productStamp = ""
productName = "anaconda"
productVersion = "bluesky"
productPath = "Packages"
productArch = None
bugUrl = "your distribution provided bug reporting tool."

if path is not None:
    f = open(path, "r")
    lines = f.readlines()
    del f
    if len(lines) >= 3:
        productStamp = lines[0][:-1]
        productArch = productStamp[productStamp.index(".")+1:]
        productName = lines[1][:-1]
        productVersion = lines[2][:-1]
    if len(lines) >= 4:
        bugUrl = lines[3][:-1]

if os.environ.has_key("ANACONDA_PRODUCTNAME"):
    productName = os.environ["ANACONDA_PRODUCTNAME"]
if os.environ.has_key("ANACONDA_PRODUCTVERSION"):
    productVersion = os.environ["ANACONDA_PRODUCTVERSION"]
if os.environ.has_key("ANACONDA_PRODUCTPATH"):
    productPath = os.environ["ANACONDA_PRODUCTPATH"]
if os.environ.has_key("ANACONDA_PRODUCTARCH"):
    productArch = os.environ["ANACONDA_PRODUCTARCH"]
if os.environ.has_key("ANACONDA_BUGURL"):
    bugUrl = os.environ["ANACONDA_BUGURL"]

if productVersion == "development": # hack to transform for now
    productVersion = "rawhide"
