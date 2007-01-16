#
# constants.py: anaconda constants
#
# Erik Troan <ewt@redhat.com>
#
# Copyright 2001 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

from rhpl.translate import _, N_

BETANAG = 0

SELINUX_DEFAULT = 1

DISPATCH_BACK = -1
DISPATCH_FORWARD = 1
DISPATCH_NOOP = None

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

# these are used for kickstart
CHECK_DEPS = 0
IGNORE_DEPS = 1
RESOLVE_DEPS = 2

# install key related constants
SKIP_KEY = -50


# pull in kickstart constants as well
from pykickstart.constants import *

# set to the number of CDs -1 the distribution currently has.  might increase
# or decrease over time
NUMBER_OF_CDS = 6


# common string needs to be easy to change
import product
productName = product.productName
productVersion = product.productVersion
productPath = product.productPath
bugzillaUrl = product.bugUrl

exceptionText = _("An unhandled exception has occurred.  This "
                  "is most likely a bug.  Please save a copy of "
                  "the detailed exception and file a bug report "
                  "against anaconda at %s" %(bugzillaUrl,))
