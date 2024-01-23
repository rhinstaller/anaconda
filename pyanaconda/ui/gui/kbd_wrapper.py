#
# Copyright (C) 2023  Red Hat, Inc.
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

"""
This module provides an API compatible dummy
replacement for the XklWrapper, for temporary
use when Anaconda runs on a Wayland compositor.

Eventually the class should be "filled in" and use
a real modern API that works on Wayland compositors
and possible even on X if we still support it
at that point.
"""

import threading

from pyanaconda.core.async_utils import async_action_wait

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

class KbdWrapper(object):
    """
    Class wrapping a keyboard access API.

    Right now this is just a dummy class
    that can be used in place of libXklavier
    when running on a Wayland compositor.

    But eventually this class should wrap
    a modern keyboard handling API that
    works on Wayland (and ideally X if we
    still support it at that point).
    """

    _instance = None
    _instance_lock = threading.Lock()

    @staticmethod
    def get_instance():
        with KbdWrapper._instance_lock:
            if not KbdWrapper._instance:
                KbdWrapper._instance = KbdWrapper()

        return KbdWrapper._instance

    def __init__(self):
        self._layout_infos = dict()
        self._layout_infos_lock = threading.RLock()
        self._switch_opt_infos = dict()
        self._switch_opt_infos_lock = threading.RLock()
        log.debug("KbdWrapper: initialized")

    def get_current_layout(self):
        """
        Get current activated X layout and variant

        :return: current activated X layout and variant (e.g. "cz (qwerty)")

        """

        log.warning("KbdWrapper: get_current_layout() - returning dummy data")
        return "cz (qwerty)"

    def get_available_layouts(self):
        """A list of layouts"""

        log.warning("KbdWrapper: get_available_layouts() - returning dummy data")
        with self._layout_infos_lock:
            return list(self._layout_infos.keys())

    def get_common_layouts(self):
        """A list of common layouts"""

        log.warning("KbdWrapper: get_common_layouts() - returning dummy data")
        return []

    def get_switching_options(self):
        """Method returning list of available layout switching options"""

        log.warning("KbdWrapper: get_switching_options() - returning dummy data")
        with self._switch_opt_infos_lock:
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
        log.warning("KbdWrapper: get_layout_variant_description() - returning dummy data")
        return "cz (qwerty)"


    def get_switch_opt_description(self, switch_opt):
        """
        Get description of the given layout switching option.

        :param switch_opt: switching option name/ID (e.g. 'grp:alt_shift_toggle')
        :type switch_opt: str
        :return: description of the layout switching option (e.g. 'Alt + Shift')
        :rtype: str

        """

        log.warning("KbdWrapper: get_switch_opt_description() - returning dummy data")
        return ""

    @async_action_wait
    def activate_default_layout(self):
        """
        Activates default layout (the first one in the list of configured
        layouts).

        """

        log.warning("KbdWrapper: activate_default_layout() - not implemented")

    def is_valid_layout(self, layout):
        """Return if given layout is valid layout or not"""

        log.warning("KbdWrapper: is_valid_layout() - not implemented (always False)")
        return False

    @async_action_wait
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

        log.warning("KbdWrapper: add_layout() - not implemented")

    @async_action_wait
    def remove_layout(self, layout):
        """
        Method that tries to remove a given layout from the current X
        configuration.

        See also the documentation for the add_layout method.

        :param layout: either 'layout' or 'layout (variant)'
        :raise XklWrapperError: if the given layout cannot be removed

        """

        log.warning("KbdWrapper: remove_layout() - not implemented")

    @async_action_wait
    def replace_layouts(self, layouts_list):
        """
        Method that replaces the layouts defined in the current X configuration
        with the new ones given.

        :param layouts_list: list of layouts defined as either 'layout' or
                             'layout (variant)'
        :raise XklWrapperError: if layouts cannot be replaced with the new ones

        """

        log.warning("KbdWrapper: replace_layouts() - not implemented")

    @async_action_wait
    def set_switching_options(self, options):
        """
        Method that sets options for layout switching. It replaces the old
        options with the new ones.

        :param options: layout switching options to be set
        :type options: list or generator
        :raise XklWrapperError: if the old options cannot be replaced with the
                                new ones

        """

        log.warning("KbdWrapper: set_switching_options() - not implemented")
