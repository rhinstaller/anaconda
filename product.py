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

if not os.access("/.buildstamp", os.R_OK):
    productName = "anaconda"
    productVersion = "bluesky"
else:
    f = open("/.buildstamp", "r")
    lines = f.readlines()
    if len(lines) < 3:
        productName = "anaconda"
        productVersion = "bluesky"
    else:
        productName = lines[1][:-1]
        productVersion = lines[2][:-1]
        

