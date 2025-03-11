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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.util import execWithRedirect
from pyanaconda.modules.common.errors.configuration import KeyboardConfigurationError
from pyanaconda.modules.common.task import Task
from pyanaconda.modules.localization.installation import write_vc_configuration
from pyanaconda.modules.localization.localization_interface import (
    KeyboardConfigurationTaskInterface,
)
from pyanaconda.modules.localization.utils import get_missing_keyboard_configuration

log = get_module_logger(__name__)


class AssignGenericKeyboardSettingTask(Task):
    """Task for assignment of generic keyboard specification to a specific configuration."""

    def __init__(self, keyboard):
        """Create a new task.

        :param keyboard: generic system keyboard specification
        :type keyboard: str
        """
        super().__init__()
        self._keyboard = keyboard

    @property
    def name(self):
        return "Assign generic keyboard setting value."

    def run(self):
        """Run assignment of generic keyboard setting value.

        :returns: tuple of X layouts and VC keyboard settings
        :rtype: (list(str), str))
        """
        x_layouts = []
        vc_keymap = ""

        if conf.system.can_activate_keyboard:
            is_keymap = try_to_load_keymap(self._keyboard)
            if is_keymap:
                vc_keymap = self._keyboard
            else:
                x_layouts.append(self._keyboard)
        else:
            vc_keymap = self._keyboard

        return x_layouts, vc_keymap


class GetMissingKeyboardConfigurationTask(Task):
    """Task for getting missing keyboard settings by conversion and default values."""

    def __init__(self, localed_wrapper, x_layouts, vc_keymap):
        """Create a new task.

        :param localed_wrapper: instance of systemd-localed service wrapper
        :type localed_wrapper: LocaledWrapper
        :param x_layouts: list of x layout specifications
        :type x_layouts: list(str)
        :param vc_keymap: virtual console keyboard mapping name
        :type vc_keymap: str
        """
        super().__init__()
        self._localed_wrapper = localed_wrapper
        self._x_layouts = x_layouts
        self._vc_keymap = vc_keymap

    def for_publication(self):
        return KeyboardConfigurationTaskInterface(self)

    @property
    def name(self):
        return "Get missing keyboard settings."

    def run(self):
        """Run getting of missing keyboard settings.

        :returns: tuple of X layouts and VC keyboard settings
        :rtype: (list(str), str))
        :raises: KeyboardConfigurationError exception when we should use unsupported layouts
                 from Live
        """
        return get_missing_keyboard_configuration(self._localed_wrapper,
                                                  self._x_layouts,
                                                  self._vc_keymap)


class ApplyKeyboardTask(Task):
    """Task for applying keyboard settings to current system."""

    def __init__(self, localed_wrapper, x_layouts, vc_keymap, switch_options):
        """Create a new task.

        :param localed_wrapper: instance of systemd-localed service wrapper
        :type localed_wrapper: LocaledWrapper
        :param x_layouts: list of x layout specifications
        :type x_layouts: list(str)
        :param vc_keymap: virtual console keyboard mapping name
        :type vc_keymap: str
        :param switch_options: list of options for layout switching
        :type switch_options: list(str)
        """
        super().__init__()
        self._localed_wrapper = localed_wrapper
        self._x_layouts = x_layouts
        self._vc_keymap = vc_keymap
        self._switch_options = switch_options

    @property
    def name(self):
        return "Apply keyboard configuration."

    def run(self):
        """Run application of keyboard settings.

        :returns: tuple of X layouts and VC keyboard settings after application
        :rtype: (list(str), str))
        """
        if not conf.system.can_activate_keyboard:
            log.debug("Activating of keyboard configuration is disabled on this system.")
            return self._x_layouts, self._vc_keymap

        if not self._vc_keymap and not self._x_layouts:
            log.debug("Not applying keyboard configuration:"
                      "neither VConsole not X Layouts are set.")
            return self._x_layouts, self._vc_keymap

        vc_keymap = self._vc_keymap
        x_layouts = self._x_layouts
        x_layouts_from_conversion = None

        if vc_keymap:
            valid_keymap = try_to_load_keymap(vc_keymap)
            if not valid_keymap:
                log.error("'%s' is not a valid VConsole keymap, not loading", vc_keymap)
                vc_keymap = ""
            else:
                # activate VConsole keymap and get converted layout and variant
                x_layouts_from_conversion = self._localed_wrapper.set_and_convert_keymap(vc_keymap)

        if not x_layouts:
            if x_layouts_from_conversion:
                # suggested by systemd-localed for a requested VConsole keymap
                x_layouts += x_layouts_from_conversion
            elif vc_keymap:
                # nothing suggested by systemd-localed, but we may try to use the
                # same string for both VConsole keymap and X layout (will fail
                # safely if it doesn't work)
                x_layouts.append(vc_keymap)

        if x_layouts:
            if not vc_keymap:
                vc_keymap = self._localed_wrapper.set_and_convert_layouts(x_layouts)

            self._localed_wrapper.set_layouts(x_layouts, self._switch_options)

            # FIXME: is this really needed?
            # Only because of configuration of the FONT, if at all.
            write_vc_configuration(vc_keymap, root="/")

        return x_layouts, vc_keymap


def try_to_load_keymap(keymap):
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
        raise KeyboardConfigurationError(msg) from oserr
    return ret == 0
