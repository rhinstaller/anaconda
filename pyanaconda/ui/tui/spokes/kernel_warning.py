#
# Copyright (C) 2019  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from simpleline.render.widgets import TextWidget

from pyanaconda.core.constants import WARNING_SMT_ENABLED_TUI
from pyanaconda.core.i18n import N_, _
from pyanaconda.core.hw import is_smt_enabled
from pyanaconda.ui.tui.spokes import StandaloneTUISpoke
from pyanaconda.ui.tui.hubs.summary import SummaryHub

__all__ = ["KernelWarningSpoke"]


class KernelWarningSpoke(StandaloneTUISpoke):
    """Spoke for kernel-related warnings."""
    preForHub = SummaryHub

    @staticmethod
    def get_screen_id():
        """Return a unique id of this UI screen."""
        return "kernel-warning"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title = N_("Warning: Processor has Simultaneous Multithreading (SMT) enabled")
        self.input_required = False

    @property
    def completed(self):
        """Show this spoke if SMT is enabled."""
        return not is_smt_enabled()

    def refresh(self, args=None):
        """Refresh the window."""
        super().refresh(args)
        self.window.add(TextWidget(_(WARNING_SMT_ENABLED_TUI)))

    def show_all(self):
        """Show the warning and close the screen."""
        super().show_all()
        self.close()

    def apply(self):
        """Nothing to apply."""
        pass
