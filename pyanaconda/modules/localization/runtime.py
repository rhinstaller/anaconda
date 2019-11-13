#
# Copyright (C) 2019 Red Hat, Inc.
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
from pyanaconda.core.constants import DEFAULT_KEYBOARD
from pyanaconda.modules.common.task import Task
from pyanaconda.keyboard import LocaledWrapper
from pyanaconda.anaconda_loggers import get_module_logger

log = get_module_logger(__name__)


class ConvertMissingKeyboardConfigurationTask(Task):
    """Task for getting missing keyboard settings by conversion."""

    def __init__(self, keyboard, x_layouts, vc_keymap):
        """Create a new task.

        TODO polish
        :param keyboard: keyboard option to be applied
        :param x_layouts: X layouts option to be applied
        :param vc_keymap: VC keymap option to be applied
        """
        super().__init__()
        self._keyboard = keyboard
        self._x_layouts = x_layouts
        self._vc_keymap = vc_keymap

    @property
    def name(self):
        return "Convert missing keyboard settings."

    def run(self):
        """Run conversion of missing keyboard settings.

        :returns: tuple of X layouts and VC keyboard settings
        :rtype: (list(str), str))
        """
        localed = LocaledWrapper()
        vc_keymap = self._vc_keymap
        x_layouts = self._x_layouts

        new_vc_keymap = ""
        if self._keyboard and not (vc_keymap or x_layouts):
            # we were given just a value in the old format, use it as a vc_keymap
            new_vc_keymap = self._keyboard
        elif not vc_keymap and x_layouts:
            new_vc_keymap = localed.convert_layouts(x_layouts)
        elif not vc_keymap:
            new_vc_keymap = DEFAULT_KEYBOARD

        if new_vc_keymap:
            vc_keymap = new_vc_keymap

        if not x_layouts:
            x_layouts = localed.convert_keymap(vc_keymap)

        return x_layouts, vc_keymap
