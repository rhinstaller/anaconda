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
from pyanaconda.core.util import execWithRedirect
from pyanaconda.core.constants import DEFAULT_KEYBOARD
from pyanaconda.modules.common.errors.configuration import KeyboardConfigurationError
from pyanaconda.modules.common.task import Task
from pyanaconda.modules.localization.localed import LocaledWrapper
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.modules.localization.installation import write_x_configuration, \
    write_vc_configuration

log = get_module_logger(__name__)


class ConvertMissingKeyboardConfigurationTask(Task):
    """Task for getting missing keyboard settings by conversion."""

    def __init__(self, keyboard, x_layouts, vc_keymap):
        """Create a new task.

        :param keyboard: generic system keyboard specification
        :type keyboard: str
        :param x_layouts: list of x layout specifications
        :type x_layouts: list(str)
        :param vc_keymap: virtual console keyboard mapping name
        :type vc_keymap: str
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


class ApplyKeyboardTask(Task):
    """Task for applying keyboard settings to current system."""

    def __init__(self, keyboard, x_layouts, vc_keymap, switch_options):
        """Create a new task.

        :param keyboard: generic system keyboard specification
        :type keyboard: str
        :param x_layouts: list of x layout specifications
        :type x_layouts: list(str)
        :param vc_keymap: virtual console keyboard mapping name
        :type vc_keymap: str
        :param switch_options: list of options for layout switching
        :type switch_options: list(str)
        """
        super().__init__()
        self._keyboard = keyboard
        self._x_layouts = x_layouts
        self._vc_keymap = vc_keymap
        self._switch_options = switch_options

    @property
    def name(self):
        return "Apply keyboard configuration."

    def _try_to_load_keymap(self, keymap):
        """
        Method that tries to load keymap and returns boolean indicating if it was
        successfull or not. It can be used to test if given string is VConsole
        keymap or not, but in case it is given valid keymap, IT REALLY LOADS IT!.

        :type keymap: string
        :raise KeyboardConfigurationError: if loadkeys command is not available
        :return: True if given string was a valid keymap and thus was loaded,
                 False otherwise
        """
        # BUG: systemd-localed should be able to tell us if we are trying to
        #      activate invalid keymap. Then we will be able to get rid of this
        #      fuction

        ret = 0
        try:
            ret = execWithRedirect("loadkeys", [keymap])
        except OSError as oserr:
            msg = "'loadkeys' command not available (%s)" % oserr.strerror
            raise KeyboardConfigurationError(msg)
        return ret == 0

    def run(self):
        """Run application of keyboard settings.

        :returns: tuple of X layouts and VC keyboard settings
        :rtype: (list(str), str))
        """
        localed = LocaledWrapper()
        vc_keymap = self._vc_keymap
        x_layouts = self._x_layouts

        if self._keyboard and not (vc_keymap or x_layouts):
            # we were given only one value in old format of the keyboard command
            # try to guess if we were given VConsole keymap or X11 layout
            is_keymap = self._try_to_load_keymap(self._keyboard)

            if is_keymap:
                vc_keymap = self._keyboard
            else:
                x_layouts.append(self._keyboard)

        if vc_keymap:
            valid_keymap = self._try_to_load_keymap(vc_keymap)
            if not valid_keymap:
                log.error("'%s' is not a valid VConsole keymap, not loading", vc_keymap)
                vc_keymap = None
            else:
                # activate VConsole keymap and get converted layout and variant
                c_lays_vars = localed.set_and_convert_keymap(vc_keymap)

        if not x_layouts:
            if c_lays_vars:
                # suggested by systemd-localed for a requested VConsole keymap
                x_layouts += c_lays_vars
            elif vc_keymap:
                # nothing suggested by systemd-localed, but we may try to use the
                # same string for both VConsole keymap and X layout (will fail
                # safely if it doesn't work)
                x_layouts.append(vc_keymap)

        if x_layouts:
            c_keymap = localed.set_and_convert_layouts(x_layouts)

            if not vc_keymap:
                vc_keymap = c_keymap

            # write out keyboard configuration for the X session
            write_x_configuration(x_layouts, self._switch_options, root="/")
            # FIXME: is this really needed?
            write_vc_configuration(vc_keymap, root="/")

        return x_layouts, vc_keymap
