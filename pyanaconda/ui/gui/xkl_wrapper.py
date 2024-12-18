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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#

import gettext
import threading
from collections import namedtuple

import iso639
from xkbregistry import rxkb

from pyanaconda import localization
from pyanaconda.core.async_utils import async_action_wait
from pyanaconda.core.string import upcase_first_letter
from pyanaconda.keyboard import normalize_layout_variant
from pyanaconda.modules.common.constants.services import LOCALIZATION

Xkb_ = lambda x: gettext.translation("xkeyboard-config", fallback=True).gettext(x)
iso_ = lambda x: gettext.translation("iso_639", fallback=True).gettext(x)

# namedtuple for information about a keyboard layout (its language and description)
LayoutInfo = namedtuple("LayoutInfo", ["langs", "desc"])

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
        self._build_layout_infos()

        self._switch_opt_infos = {}
        self._build_switch_opt_infos()

    def _build_layout_infos(self):
        for layout in self._rxkb.layouts.values():
            name = layout.name
            if layout.variant:
                name += ' (' + layout.variant + ')'

            langs = []
            for lang in layout.iso639_codes:
                if iso639.find(iso639_2=lang):
                    langs.append(iso639.to_name(lang))

            if name not in self._layout_infos:
                self._layout_infos[name] = LayoutInfo(langs, layout.description)
            else:
                self._layout_infos[name].langs.extend(langs)

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
        Get description of the given layout-variant.

        :param layout_variant: layout-variant specification (e.g. 'cz (qwerty)')
        :type layout_variant: str
        :param with_lang: whether to include language of the layout-variant (if defined)
                          in the description or not
        :type with_lang: bool
        :param xlated: whethe to return translated or english version of the description
        :type xlated: bool
        :return: description of the layout-variant specification (e.g. 'Czech (qwerty)')
        :rtype: str

        """

        layout_info = self._layout_infos[layout_variant]
        lang = ""
        # translate language and upcase its first letter, translate the
        # layout-variant description
        if xlated:
            if len(layout_info.langs) == 1:
                lang = iso_(layout_info.langs[0])
            description = Xkb_(layout_info.desc)
        else:
            if len(layout_info.langs) == 1:
                lang = upcase_first_letter(layout_info.langs[0])
            description = layout_info.desc

        if with_lang and lang:
            # ISO language/country names can be things like
            # "Occitan (post 1500); Provencal", or
            # "Iran, Islamic Republic of", or "Greek, Modern (1453-)"
            # or "Catalan; Valencian": let's handle that gracefully
            # let's also ignore case, e.g. in French all translated
            # language names are lower-case for some reason
            checklang = lang.split()[0].strip(",;").lower()
            if checklang not in description.lower():
                return "%s (%s)" % (lang, description)

        return description

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
