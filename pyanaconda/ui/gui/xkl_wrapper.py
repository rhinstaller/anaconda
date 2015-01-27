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
# Red Hat Author(s): Vratislav Podzimek <vpodzime@redhat.com>
#

"""
This module include functions and classes for dealing with multiple layouts in
Anaconda. It wraps the libxklavier functionality to protect Anaconda from
dealing with its "nice" API that looks like a Lisp-influenced "good old C" and
also systemd-localed functionality.

It provides a XklWrapper class with several methods that can be used for listing
and various modifications of keyboard layouts settings.

"""

import threading
import gettext
from gi.repository import GdkX11, Xkl
from collections import namedtuple

from pyanaconda import flags
from pyanaconda import iutil
from pyanaconda.constants import DEFAULT_KEYBOARD
from pyanaconda.keyboard import join_layout_variant, parse_layout_variant, KeyboardConfigError, InvalidLayoutVariantSpec
from pyanaconda.ui.gui.utils import gtk_action_wait

import logging
log = logging.getLogger("anaconda")

Xkb_ = lambda x: gettext.ldgettext("xkeyboard-config", x)
iso_ = lambda x: gettext.ldgettext("iso_639", x)

# namedtuple for information about a keyboard layout (its language and description)
LayoutInfo = namedtuple("LayoutInfo", ["lang", "desc"])

class XklWrapperError(KeyboardConfigError):
    """Exception class for reporting libxklavier-related problems"""

    pass

class XklWrapper(object):
    """
    Class wrapping the libxklavier functionality

    Use this class as a singleton class because it provides read-only data
    and initialization (that takes quite a lot of time) reads always the
    same data. It doesn't have sense to make multiple instances

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
        #initialize Xkl-related stuff
        display = GdkX11.x11_get_default_xdisplay()
        self._engine = Xkl.Engine.get_instance(display)

        self._rec = Xkl.ConfigRec()
        if not self._rec.get_from_server(self._engine):
            raise XklWrapperError("Failed to get configuration from server")

        #X is probably initialized to the 'us' layout without any variant and
        #since we want to add layouts with variants we need the layouts and
        #variants lists to have the same length. Add "" padding to variants.
        #See docstring of the add_layout method for details.
        diff = len(self._rec.layouts) - len(self._rec.variants)
        if diff > 0 and flags.can_touch_runtime_system("activate layouts"):
            self._rec.set_variants(self._rec.variants + (diff * [""]))
            if not self._rec.activate(self._engine):
                # failed to activate layouts given e.g. by a kickstart (may be
                # invalid)
                lay_var_str = ",".join(map(join_layout_variant,
                                           self._rec.layouts,
                                           self._rec.variants))
                log.error("Failed to activate layouts: '%s', "
                          "falling back to default %s", lay_var_str, DEFAULT_KEYBOARD)
                self._rec.set_layouts([DEFAULT_KEYBOARD])
                self._rec.set_variants([""])

                if not self._rec.activate(self._engine):
                    # failed to activate even the default layout, something is
                    # really wrong
                    raise XklWrapperError("Failed to initialize layouts")

        #needed also for Gkbd.KeyboardDrawingDialog
        self.configreg = Xkl.ConfigRegistry.get_instance(self._engine)
        self.configreg.load(False)

        self._layout_infos = dict()
        self._switch_opt_infos = dict()

        #this might take quite a long time
        self.configreg.foreach_language(self._get_language_variants, None)
        self.configreg.foreach_country(self._get_country_variants, None)

        #'grp' means that we want layout (group) switching options
        self.configreg.foreach_option('grp', self._get_switch_option, None)

    def _get_lang_variant(self, c_reg, item, subitem, lang):
        if subitem:
            name = item.get_name() + " (" + subitem.get_name() + ")"
            description = subitem.get_description()
        else:
            name = item.get_name()
            description = item.get_description()

        #if this layout has already been added for some other language,
        #do not add it again (would result in duplicates in our lists)
        if name not in self._layout_infos:
            self._layout_infos[name] = LayoutInfo(lang, description)

    def _get_country_variant(self, c_reg, item, subitem, country):
        if subitem:
            name = item.get_name() + " (" + subitem.get_name() + ")"
            description = subitem.get_description()
        else:
            name = item.get_name()
            description = item.get_description()

        # if the layout was not added with any language, add it with a country
        if name not in self._layout_infos:
            self._layout_infos[name] = LayoutInfo(country, description)

    def _get_language_variants(self, c_reg, item, user_data=None):
        lang_name, lang_desc = item.get_name(), item.get_description()

        c_reg.foreach_language_variant(lang_name, self._get_lang_variant, lang_desc)

    def _get_country_variants(self, c_reg, item, user_data=None):
        country_name, country_desc = item.get_name(), item.get_description()

        c_reg.foreach_country_variant(country_name, self._get_country_variant,
                                      country_desc)

    def _get_switch_option(self, c_reg, item, user_data=None):
        """Helper function storing layout switching options in foreach cycle"""
        desc = item.get_description()
        name = item.get_name()

        self._switch_opt_infos[name] = desc

    def get_current_layout(self):
        """
        Get current activated X layout and variant

        :return: current activated X layout and variant (e.g. "cz (qwerty)")

        """
        # ported from the widgets/src/LayoutIndicator.c code

        self._engine.start_listen(Xkl.EngineListenModes.TRACK_KEYBOARD_STATE)
        state = self._engine.get_current_state()
        cur_group = state.group
        num_groups = self._engine.get_num_groups()

        # BUG?: if the last layout in the list is activated and removed,
        #       state.group may be equal to n_groups
        if cur_group >= num_groups:
            cur_group = num_groups - 1

        layout = self._rec.layouts[cur_group]
        try:
            variant = self._rec.variants[cur_group]
        except IndexError:
            # X server may have forgotten to add the "" variant for its default layout
            variant = ""

        self._engine.stop_listen(Xkl.EngineListenModes.TRACK_KEYBOARD_STATE)

        return join_layout_variant(layout, variant)

    def get_available_layouts(self):
        """A generator yielding layouts (no need to store them as a bunch)"""

        return self._layout_infos.keys()

    def get_switching_options(self):
        """Method returning list of available layout switching options"""

        return self._switch_opt_infos.keys()

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

        # translate language and upcase its first letter, translate the
        # layout-variant description
        if xlated:
            lang = iutil.upcase_first_letter(iso_(layout_info.lang).decode("utf-8"))
            description = Xkb_(layout_info.desc).decode("utf-8")
        else:
            lang = iutil.upcase_first_letter(layout_info.lang)
            description = layout_info.desc

        if with_lang and lang and not description.startswith(lang):
            return "%s (%s)" % (lang, description)
        else:
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

    @gtk_action_wait
    def activate_default_layout(self):
        """
        Activates default layout (the first one in the list of configured
        layouts).

        """

        self._engine.lock_group(0)

    def is_valid_layout(self, layout):
        """Return if given layout is valid layout or not"""

        return layout in self._layout_infos

    @gtk_action_wait
    def add_layout(self, layout):
        """
        Method that tries to add a given layout to the current X configuration.

        The X layouts configuration is handled by two lists. A list of layouts
        and a list of variants. Index-matching items in these lists (as if they
        were zipped) are used for the construction of real layouts (e.g.
        'cz (qwerty)').

        :param layout: either 'layout' or 'layout (variant)'
        :raise XklWrapperError: if the given layout is invalid or cannot be added

        """

        try:
            #we can get 'layout' or 'layout (variant)'
            (layout, variant) = parse_layout_variant(layout)
        except InvalidLayoutVariantSpec as ilverr:
            raise XklWrapperError("Failed to add layout: %s" % ilverr)

        #do not add the same layout-variant combinanion multiple times
        if (layout, variant) in zip(self._rec.layouts, self._rec.variants):
            return

        self._rec.set_layouts(self._rec.layouts + [layout])
        self._rec.set_variants(self._rec.variants + [variant])

        if not self._rec.activate(self._engine):
            raise XklWrapperError("Failed to add layout '%s (%s)'" % (layout,
                                                                      variant))

    @gtk_action_wait
    def remove_layout(self, layout):
        """
        Method that tries to remove a given layout from the current X
        configuration.

        See also the documentation for the add_layout method.

        :param layout: either 'layout' or 'layout (variant)'
        :raise XklWrapperError: if the given layout cannot be removed

        """

        #we can get 'layout' or 'layout (variant)'
        (layout, variant) = parse_layout_variant(layout)

        layouts_variants = zip(self._rec.layouts, self._rec.variants)

        if not (layout, variant) in layouts_variants:
            msg = "'%s (%s)' not in the list of added layouts" % (layout,
                                                                  variant)
            raise XklWrapperError(msg)

        idx = layouts_variants.index((layout, variant))
        new_layouts = self._rec.layouts[:idx] + self._rec.layouts[(idx + 1):]
        new_variants = self._rec.variants[:idx] + self._rec.variants[(idx + 1):]

        self._rec.set_layouts(new_layouts)
        self._rec.set_variants(new_variants)

        if not self._rec.activate(self._engine):
            raise XklWrapperError("Failed to remove layout '%s (%s)'" % (layout,
                                                                       variant))

    @gtk_action_wait
    def replace_layouts(self, layouts_list):
        """
        Method that replaces the layouts defined in the current X configuration
        with the new ones given.

        :param layouts_list: list of layouts defined as either 'layout' or
                             'layout (variant)'
        :raise XklWrapperError: if layouts cannot be replaced with the new ones

        """

        new_layouts = list()
        new_variants = list()

        for layout_variant in layouts_list:
            (layout, variant) = parse_layout_variant(layout_variant)
            new_layouts.append(layout)
            new_variants.append(variant)

        self._rec.set_layouts(new_layouts)
        self._rec.set_variants(new_variants)

        if not self._rec.activate(self._engine):
            msg = "Failed to replace layouts with: %s" % ",".join(layouts_list)
            raise XklWrapperError(msg)

    @gtk_action_wait
    def set_switching_options(self, options):
        """
        Method that sets options for layout switching. It replaces the old
        options with the new ones.

        :param options: layout switching options to be set
        :type options: list or generator
        :raise XklWrapperError: if the old options cannot be replaced with the
                                new ones

        """

        #preserve old "non-switching options"
        new_options = [opt for opt in self._rec.options if "grp:" not in opt]
        new_options += options

        self._rec.set_options(new_options)

        if not self._rec.activate(self._engine):
            msg = "Failed to set switching options to: %s" % ",".join(options)
            raise XklWrapperError(msg)

