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

import re
import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)
N_ = lambda x: x

SELINUX_DEFAULT = 1

DISPATCH_BACK = -1
DISPATCH_FORWARD = 1
DISPATCH_DEFAULT = None
DISPATCH_WAITING = 2

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
bugzillaUrl = product.bugUrl
isFinal = product.isFinal

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
DD_ALL = "/tmp/DD"
DD_EXTRACTED = re.compile("/lib/modules/[^/]+/updates/DD/(?P<moduledir>.*/)?(?P<modulename>[^/.]+).ko.*")
DD_FIRMWARE = "/tmp/DD/lib/firmware"
DD_RPMS = "/tmp/DD-*"

TRANSLATIONS_UPDATE_DIR="/tmp/updates/po"

ANACONDA_CLEANUP = "anaconda-cleanup"
ROOT_PATH = "/mnt/sysimage"
