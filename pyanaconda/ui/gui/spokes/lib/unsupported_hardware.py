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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from pyanaconda.core.util import detect_unsupported_hardware
from pyanaconda.ui.gui import GUIObject

__all__ = ["UnsupportedHardwareDialog"]


class UnsupportedHardwareDialog(GUIObject):
    """Dialog for warnings about unsupported hardware.

    Show this dialog if the unsupported hardware was detected.
    """
    builderObjects = ["unsupportedHardwareDialog"]
    mainWidgetName = "unsupportedHardwareDialog"
    uiFile = "spokes/lib/unsupported_hardware.glade"

    def __init__(self, data):
        super().__init__(data)
        self._warnings = detect_unsupported_hardware()

    @property
    def supported(self):
        return not self._warnings

    def refresh(self):
        message_label = self.builder.get_object("messageLabel")
        message_label.set_label("\n\n".join(self._warnings))

    def run(self):
        rc = self.window.run()
        self.window.destroy()
        return rc
