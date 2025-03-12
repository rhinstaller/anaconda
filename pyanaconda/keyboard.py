#
# Copyright (C) 2012  Red Hat, Inc.
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

"""
This module provides functions for dealing with keyboard layouts/keymaps in Anaconda.
"""

import re

import langtable

from pyanaconda import localization
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import DEFAULT_KEYBOARD
from pyanaconda.modules.common.constants.services import LOCALIZATION
from pyanaconda.modules.common.task import sync_run_task

log = get_module_logger(__name__)


# should match and parse strings like 'cz' or 'cz (qwerty)' regardless of white
# space
LAYOUT_VARIANT_RE = re.compile(r'^\s*([/\w]+)\s*'  # layout plus
                               r'(?:(?:\(\s*([-\w]+)\s*\))'  # variant in parentheses
                               r'|(?:$))\s*')  # or nothing


class KeyboardConfigError(Exception):
    """Exception class for keyboard configuration related problems"""

    pass


class InvalidLayoutVariantSpec(Exception):
    """
    Exception class for errors related to parsing layout and variant specification strings.

    """

    pass


def can_configure_keyboard():
    """Can we configure the keyboard?

    NOTE:
    This function could be inlined, however, this give us a possibility for future limitation
    when needed. For example we could use this method to limit keyboard configuration if we
    are able to detect that current system doesn't support localed keyboard layout switching.
    """
    return conf.system.can_configure_keyboard


def parse_layout_variant(layout_variant_str):
    """
    Parse layout and variant from the string that may look like 'layout' or
    'layout (variant)'.

    :param layout_variant_str: keyboard layout and variant string specification
    :type layout_variant_str: str
    :return: the (layout, variant) pair, where variant can be ""
    :rtype: tuple
    :raise InvalidLayoutVariantSpec: if the given string isn't a valid layout
                                     and variant specification string

    """

    match = LAYOUT_VARIANT_RE.match(layout_variant_str)
    if not match:
        msg = "'%s' is not a valid keyboard layout and variant specification" % layout_variant_str
        raise InvalidLayoutVariantSpec(msg)

    layout, variant = match.groups()

    # groups may be (layout, None) if no variant was specified
    return (layout, variant or "")


def join_layout_variant(layout, variant=""):
    """
    Join layout and variant to form the commonly used 'layout (variant)'
    or 'layout' (if variant is missing) format.

    :type layout: string
    :type variant: string
    :return: 'layout (variant)' or 'layout' string
    :rtype: string

    """

    if variant:
        return "%s (%s)" % (layout, variant)
    else:
        return layout


def normalize_layout_variant(layout_str):
    """
    Normalize keyboard layout and variant specification given as a single
    string. E.g. for a 'layout(variant) string missing the space between the
    left parenthesis return 'layout (variant)' which is a proper layout and
    variant specification we use.

    :param layout_str: a string specifying keyboard layout and its variant
    :type layout_str: string

    """

    layout, variant = parse_layout_variant(layout_str)
    return join_layout_variant(layout, variant)


def populate_missing_items(localization_proxy=None):
    """
    Function that populates virtual console keymap and X layouts if they
    are missing. By invoking systemd-localed methods this function READS AND
    WRITES CONFIGURATION FILES (but tries to keep their content unchanged).

    :param localization_proxy: DBus proxy of the localization module or None

    """
    task_path = localization_proxy.PopulateMissingKeyboardConfigurationWithTask()
    task_proxy = LOCALIZATION.get_proxy(task_path)
    sync_run_task(task_proxy)


def activate_keyboard(localization_proxy):
    """
    Try to setup VConsole keymap and X11 layouts as specified in kickstart.

    :param localization_proxy: DBus proxy of the localization module or None

    """
    task_path = localization_proxy.ApplyKeyboardWithTask()
    task_proxy = LOCALIZATION.get_proxy(task_path)
    sync_run_task(task_proxy)


def set_x_keyboard_defaults(localization_proxy, xkl_wrapper):
    """
    Set default keyboard settings (layouts, layout switching).

    :param localization_proxy: DBus proxy of the localization module or None
    :type ksdata: object instance
    :param xkl_wrapper: XklWrapper instance
    :type xkl_wrapper: object instance
    :raise InvalidLocaleSpec: if an invalid locale is given (see
                              localization.is_valid_langcode)
    """
    x_layouts = localization_proxy.XLayouts
    # remove all X layouts that are not valid X layouts (unsupported)
    valid_layouts = []
    for layout in x_layouts:
        if xkl_wrapper.is_valid_layout(layout):
            valid_layouts.append(layout)
    localization_proxy.XLayouts = valid_layouts

    if valid_layouts:
        # do not add layouts if there are any specified in the kickstart
        # (the x_layouts list comes from kickstart)
        return

    locale = localization_proxy.Language
    layouts = localization.get_locale_keyboards(locale)
    if layouts:
        # take the first locale (with highest rank) from the list and
        # store it normalized
        new_layouts = [normalize_layout_variant(layouts[0])]
        # annoyingly, langtable expects *no* space between layout and
        # (variant) here
        if not langtable.supports_ascii(layouts[0].replace(" ", "")):
            # The default keymap setting should have "us" before the native layout
            # which does not support ascii,
            # refer: https://bugzilla.redhat.com/show_bug.cgi?id=1039185
            new_layouts.insert(0, DEFAULT_KEYBOARD)
    else:
        log.error("Failed to get layout for chosen locale '%s'", locale)
        new_layouts = [DEFAULT_KEYBOARD]

    localization_proxy.XLayouts = new_layouts

    if can_configure_keyboard():
        xkl_wrapper.replace_layouts(new_layouts)

    if len(new_layouts) >= 2 and not localization_proxy.LayoutSwitchOptions:
        # initialize layout switching if needed
        localization_proxy.LayoutSwitchOptions = ["grp:alt_shift_toggle"]

        if can_configure_keyboard():
            xkl_wrapper.set_switching_options(["grp:alt_shift_toggle"])
            # activate the language-default layout instead of the additional
            # one
            xkl_wrapper.activate_default_layout()
