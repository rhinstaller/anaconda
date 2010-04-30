#
# constants.py: anaconda constants
#
# Copyright (C) 2001  Red Hat, Inc.  All rights reserved.
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
# Author(s): Erik Troan <ewt@redhat.com>
#

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)
N_ = lambda x: x

BETANAG = 0

SELINUX_DEFAULT = 1

DISPATCH_BACK = -1
DISPATCH_FORWARD = 1
DISPATCH_NOOP = None

EXN_OK = 0
EXN_DEBUG = 1
EXN_SAVE = 2
EXN_CANCEL = 3

# different types of partition requests
# REQUEST_PREEXIST is a placeholder for a pre-existing partition on the system
# REQUEST_NEW is a request for a partition which will be automatically
#              created based on various constraints on size, drive, etc
# REQUEST_RAID is a request for a raid device
# REQUEST_PROTECTED is a preexisting partition which can't change
#              (harddrive install, harddrive with the isos on it)
#
REQUEST_PREEXIST = 1
REQUEST_NEW = 2
REQUEST_RAID = 4
REQUEST_PROTECTED = 8
REQUEST_VG = 16 # volume group
REQUEST_LV = 32 # logical volume

# XXX this is made up and used by the size spinner; should just be set with
# a callback
MAX_PART_SIZE = 1024*1024*1024

# install key related constants
SKIP_KEY = -50

# pull in kickstart constants as well
from pykickstart.constants import *

# common string needs to be easy to change
import product
productName = product.productName
productVersion = product.productVersion
productArch = product.productArch
productPath = product.productPath
bugzillaUrl = product.bugUrl

lvmErrorOutput = "/tmp/lvmout"

exceptionText = _("An unhandled exception has occurred.  This "
                  "is most likely a bug.  Please save a copy of "
                  "the detailed exception and file a bug report")
if not bugzillaUrl:
    # this string will be combined with "An unhandled exception"...
    # the leading space is not a typo.
    exceptionText += _(" with the provider of this software.")
else:
    # this string will be combined with "An unhandled exception"...
    # the leading space is not a typo.
    exceptionText += _(" against anaconda at %s") %(bugzillaUrl,)

# DriverDisc Paths
DD_EXTRACTED = "/tmp/DD"
DD_RPMS = "/tmp/DD-*"

