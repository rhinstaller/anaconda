# Performance text spoke
#
# Copyright (C) 2018  Red Hat, Inc.
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


from pyanaconda import iutil

from pyanaconda.flags import flags
from pyanaconda.i18n import N_, _

from pyanaconda.ui.helpers import find_bootopt_mitigations, set_bootopt_mitigations
from pyanaconda.ui.categories.system import SystemCategory
from pyanaconda.ui.tui.spokes import EditTUISpoke
from pyanaconda.ui.tui.spokes import EditTUISpokeEntry as Entry

__all__ = ["PerformanceSpoke"]

class PerformanceSpoke(EditTUISpoke):
    """ The Kernel & performance spoke provides tunables for
    certain security mitigations, that are kernel based and
    might incur a performance penalty.
    """
    title = N_("Kernel & performance")
    category = SystemCategory

    edit_fields = [
        Entry("PTI (Page Table Isolation)", "pti", EditTUISpoke.CHECK, True),
        Entry("IBRS (Indirect Branch Restricted Speculation)", "ibrs", EditTUISpoke.CHECK, True),
        Entry("IBPB (Indirect Branch Prediction Barriers)", "ibpb", EditTUISpoke.CHECK, True),
        ]

    def __init__(self, app, data, storage, payload, instclass):
        EditTUISpoke.__init__(self, app, data, storage, payload, instclass)
        self.initialize_start()

        self.args = iutil.DataHolder(pti=True, ibrs=True, ibpb=True)

        # some mitigations might be disabled in the input kickstart
        disabled_mitigations = find_bootopt_mitigations(self.data.bootloader.appendLine)

        # set the TUI checkboxes accordingly
        self.args.pti = not disabled_mitigations.no_pti
        self.args.ibrs = not disabled_mitigations.no_ibrs
        self.args.ibpb = not disabled_mitigations.no_ibpb

        self.initialize_done()

    @property
    def completed(self):
        """Every state of the mitigation options should be valid."""
        return True

    @property
    def mandatory(self):
        return False

    @property
    def status(self):
        # set based on mitigations being turned ON/OFF
        all_enabled = all([self.args.pti, self.args.ibrs, self.args.ibpb])
        if all_enabled:
            return _("All mitigations enabled.")
        else:
            return _("Some mitigations disabled.")

    def input(self, args, key):
        return EditTUISpoke.input(self, args, key)

    def apply(self):
        # set boot options accordingly
        opts = set_bootopt_mitigations(opts=self.data.bootloader.appendLine,
                                       no_pti=not self.args.pti,
                                       no_ibrs=not self.args.ibrs,
                                       no_ibpb=not self.args.ibpb)
        self.data.bootloader.appendLine = opts
