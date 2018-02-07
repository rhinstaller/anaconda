# performance spoke class
#
# Copyright (C) 2018 Red Hat, Inc.
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
# Red Hat Author(s): Martin Kolman <mkolman@redhat.com>
#

from pyanaconda.flags import flags
from pyanaconda.i18n import _, CN_

from pyanaconda.ui.helpers import find_bootopt_mitigations, set_bootopt_mitigations
from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.categories.system import SystemCategory

import logging
log = logging.getLogger("anaconda")

__all__ = ["PerformanceSpoke"]


class PerformanceSpoke(NormalSpoke):
    """ The Kernel & Performance spoke provides tunables for
    certain security mitigations, that are kernel based and
    might incur a performance penalty.
    """

    builderObjects = ["performanceWindow"]

    mainWidgetName = "performanceWindow"
    uiFile = "spokes/performance.glade"
    helpFile = "PerformanceSpoke.xml"

    category = SystemCategory

    title = CN_("GUI|Spoke", "_KERNEL & PERFORMANCE")
    icon = "system-run-symbolic"

    def __init__(self, *args):
        NormalSpoke.__init__(self, *args)
        self._pti_switch = self.builder.get_object("switch_pti")
        self._ibrs_switch = self.builder.get_object("switch_ibrs")
        self._ibpb_switch = self.builder.get_object("switch_ibpb")

    def initialize(self):
        NormalSpoke.initialize(self)
        self.initialize_start()

        # some mitigations might be disabled in the input kickstart
        disabled_mitigations = find_bootopt_mitigations(self.data.bootloader.appendLine)

        # set the switches accordingly
        self._pti_switch.set_active(not disabled_mitigations.no_pti)
        self._ibrs_switch.set_active(not disabled_mitigations.no_ibrs)
        self._ibpb_switch.set_active(not disabled_mitigations.no_ibpb)

        # report that we are done
        self.initialize_done()

    @property
    def status(self):
        # set based on mitigations being turned ON/OFF
        all_enabled = all([self._pti_switch.get_active(),
                           self._ibrs_switch.get_active(),
                           self._ibpb_switch.get_active()])
        if all_enabled:
            return _("All mitigations enabled")
        else:
            return _("Some mitigations disabled")

    @property
    def mandatory(self):
        return False

    def apply(self):
        # set boot options accordingly
        opts = set_bootopt_mitigations(opts=self.data.bootloader.appendLine,
                                       no_pti=not self._pti_switch.get_active(),
                                       no_ibrs=not self._ibrs_switch.get_active(),
                                       no_ibpb=not self._ibpb_switch.get_active())
        self.data.bootloader.appendLine = opts

    @property
    def completed(self):
        """Every state of the mitigation options should be valid."""
        return True

    @property
    def sensitive(self):
        return True
