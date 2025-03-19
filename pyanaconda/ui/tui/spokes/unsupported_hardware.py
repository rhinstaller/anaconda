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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from simpleline.render.widgets import TextWidget

from pyanaconda.ui.tui.spokes import StandaloneTUISpoke
from pyanaconda.ui.tui.hubs.summary import SummaryHub
from pyanaconda.core.i18n import N_
from pyanaconda.core.util import detect_unsupported_hardware

__all__ = ["UnsupportedHardwareSpoke"]


class UnsupportedHardwareSpoke(StandaloneTUISpoke):
    """Spoke for warnings about unsupported hardware.

    Show this spoke if the unsupported hardware was detected.
    """
    preForHub = SummaryHub
    priority = -10

    @staticmethod
    def get_screen_id():
        """Return a unique id of this UI screen."""
        return "unsupported-hardware-warning"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title = N_("Unsupported Hardware Detected")
        self._warnings = detect_unsupported_hardware()

    @property
    def completed(self):
        return not self._warnings

    def refresh(self, args=None):
        super().refresh(args)

        for warning in self._warnings:
            self.window.add_with_separator(TextWidget(warning))

    def apply(self):
        pass
