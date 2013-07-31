# Ask vnc text spoke
#
# Copyright (C) 2013  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Brian C. Lane <bcl@redhat.com>
#

from pyanaconda.ui.tui.spokes import StandaloneTUISpoke
from pyanaconda.ui.tui.simpleline import TextWidget
from pyanaconda.ui.tui.hubs.summary import SummaryHub
from pyanaconda.i18n import _

from pyanaconda.iutil import is_unsupported_hw
from pyanaconda.product import productName

import logging
log = logging.getLogger("anaconda")

__all__ = ["WarningsSpoke"]

class WarningsSpoke(StandaloneTUISpoke):
    title = _("Warnings")

    preForHub = SummaryHub
    priority = 0

    def __init__(self, *args, **kwargs):
        StandaloneTUISpoke.__init__(self, *args, **kwargs)

        self._message = _("This hardware (or a combination thereof) is not "
                          "supported by Red Hat.  For more information on "
                          "supported hardware, please refer to "
                          "http://www.redhat.com/hardware." )
        # Does anything need to be displayed?
        self._unsupported = productName.startswith("Red Hat Enterprise Linux") and \
                            is_unsupported_hw() and \
                            not self.data.unsupportedhardware.unsupported_hardware

    @property
    def completed(self):
        return not self._unsupported

    def refresh(self, args = None):
        StandaloneTUISpoke.refresh(self, args)

        self._window += [TextWidget(self._message), ""]

        return True

