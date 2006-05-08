#
# product.py: product identification string
#
# Copyright 2003 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

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
productPath = "anaconda"
bugUrl = "your distribution provided bug reporting tool."

if path is not None:
    f = open(path, "r")
    lines = f.readlines()
    if len(lines) >= 3:
        productStamp = lines[0][:-1]
        productName = lines[1][:-1]
        productVersion = lines[2][:-1]
    if len(lines) >= 4:
	productPath = lines[3][:-1]
    if len(lines) >= 5:
        bugUrl = lines[4][:-1]

if os.environ.has_key("ANACONDA_PRODUCTNAME"):
    productName = os.environ["ANACONDA_PRODUCTNAME"]
if os.environ.has_key("ANACONDA_PRODUCTVERSION"):
    productVersion = os.environ["ANACONDA_PRODUCTVERSION"]
if os.environ.has_key("ANACONDA_PRODUCTPATH"):
    productPath = os.environ["ANACONDA_PRODUCTPATH"]
if os.environ.has_key("ANACONDA_BUGURL"):
    bugUrl = os.environ["ANACONDA_BUGURL"]
