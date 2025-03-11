#
# Copyright (C) 2012-2014  Red Hat, Inc.
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

import gettext
import threading

from xkbregistry import rxkb

from pyanaconda import localization
from pyanaconda.core.async_utils import async_action_wait
from pyanaconda.keyboard import normalize_layout_variant
from pyanaconda.localization import _build_layout_infos, _get_layout_variant_description
from pyanaconda.modules.common.constants.services import LOCALIZATION

Xkb_ = lambda x: gettext.translation("xkeyboard-config", fallback=True).gettext(x)

class XklWrapper:
    """
    Class that used to wrap libxklavier functionality.

    libxklavier is deprecated and X11-only. On RHEL, the GNOME Kiosk API is used
    instead. This class is kept to keep make the code migration as simple as
    possible.
    """

    _instance = None
    _instance_lock = threading.Lock()

    @staticmethod
    def get_instance():
        with XklWrapper._instance_lock:
            if not XklWrapper._instance:
                XklWrapper._instance = XklWrapper()

        return XklWrapper._instance

    def __init__(self):
        self._keyboard_manager = LOCALIZATION.get_proxy()
        self._switching_options = []

        self._rxkb = rxkb.Context()

        self._layout_infos = {}
        self._layout_infos = _build_layout_infos()

        self._switch_opt_infos = {}
        self._build_switch_opt_infos()


    def _build_switch_opt_infos(self):
        for group in self._rxkb.option_groups:
            # 'grp' means that we want layout (group) switching options
            if group.name != 'grp':
                continue

            for option in group.options.values():
                self._switch_opt_infos[option.name] = option.description

    @property
    def compositor_selected_layout_changed(self):
        """Signal emitted when the selected keyboard layout changes."""
        return self._keyboard_manager.CompositorSelectedLayoutChanged

    @property
    def compositor_layouts_changed(self):
        """Signal emitted when available layouts change."""
        return self._keyboard_manager.CompositorLayoutsChanged

    @async_action_wait
    def get_current_layout(self):
        """
        Get current activated layout and variant

        :return: current activated layout and variant (e.g. "cz (qwerty)")

        :raise KeyboardConfigError: if layouts with invalid backend type is found
        """

        return self._keyboard_manager.GetCompositorSelectedLayout()

    def get_available_layouts(self):
        """A list of layouts"""

        return list(self._layout_infos.keys())

    def get_common_layouts(self):
        """A list of common layouts"""

        return list(set(map(
            normalize_layout_variant, localization.get_common_keyboard_layouts()
        )).intersection(set(self.get_available_layouts())))

    def get_switching_options(self):
        """Method returning list of available layout switching options"""

        return list(self._switch_opt_infos.keys())

    def get_layout_variant_description(self, layout_variant, with_lang=True, xlated=True):
        """
        Return a description of the given layout-variant.

        :param layout_variant: Layout-variant identifier (e.g., 'cz (qwerty)')
        :param with_lang: Include the language in the description if available
        :param xlated: Return a translated version of the description if True
        :return: Formatted layout description
        """

        return _get_layout_variant_description(layout_variant, self._layout_infos, with_lang, xlated)

    def get_switch_opt_description(self, switch_opt):
        """
        Get description of the given layout switching option.

        :param switch_opt: switching option name/ID (e.g. 'grp:alt_shift_toggle')
        :type switch_opt: str
        :return: description of the layout switching option (e.g. 'Alt + Shift')
        :rtype: str

        """

        # translate the description of the switching option
        return Xkb_(self._switch_opt_infos[switch_opt])

    @async_action_wait
    def activate_default_layout(self):
        """
        Activates default layout (the first one in the list of configured
        layouts).

        :raise KeyboardConfigError: if layouts with invalid backend type is found
        """

        layouts = self._keyboard_manager.GetCompositorLayouts()
        if not layouts:
            return

        self._keyboard_manager.SetCompositorSelectedLayout(layouts[0])

    def is_valid_layout(self, layout):
        """Return if given layout is valid layout or not"""

        return layout in self._layout_infos

    @async_action_wait
    def replace_layouts(self, layouts_list):
        """
        Method that replaces the layouts defined in the current configuration
        with the new ones given.

        :param layouts_list: list of layouts defined as either 'layout' or
                             'layout (variant)'
        """

        self._keyboard_manager.SetCompositorLayouts(layouts_list, self._switching_options)

    @async_action_wait
    def set_switching_options(self, options):
        """
        Method that sets options for layout switching. It replaces the old
        options with the new ones.

        :param options: layout switching options to be set
        :type options: list or generator

        :raise KeyboardConfigError: if layouts with invalid backend type is found
        """

        #preserve old "non-switching options"
        new_options = [opt for opt in self._switching_options if "grp:" not in opt]
        new_options += options
        self._switching_options = new_options

        layouts = self._keyboard_manager.GetCompositorLayouts()
        if not layouts:
            return

        self._keyboard_manager.SetCompositorLayouts(layouts, self._switching_options)
