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

DISPATCH_BACK = -1
DISPATCH_FORWARD = 1
DISPATCH_NOOP = None

# these are used for kickstart
CHECK_DEPS = 0
IGNORE_DEPS = 1
RESOLVE_DEPS = 2

# common string needs to be easy to change
import product
productName = product.productName
