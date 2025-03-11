#
# Copyright (C) 2023 Red Hat, Inc.
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
from pyanaconda.core.constants import DEFAULT_KEYBOARD
from pyanaconda.modules.localization.live_keyboard import get_live_keyboard_instance

log = get_module_logger(__name__)


def get_missing_keyboard_configuration(localed_wrapper, x_layouts, vc_keymap):
    """Get keyboard configuration if not set by user.

    Algorithm works as this:
    1. Check if full keyboard configuration is already set
       -> return these
    2. If no X layouts, check if they can be obtained from live system
       -> read X layouts
    3a. If still no configuration is present
       -> use DEFAULT_KEYBOARD as console layout and fall through to...
    3b. If only one of the keyboard layout or virtual console keymap is set
       -> convert one to the other by localed

    :param localed_wrapper: instance of systemd-localed service wrapper
    :type localed_wrapper: LocaledWrapper
    :param x_layouts: list of X layout specifications
    :type x_layouts: list(str)
    :param vc_keymap: virtual console keyboard mapping name
    :type vc_keymap: str
    :returns: tuple of X layouts and VC keyboard settings
    :rtype: (list(str), str))
    """
    if vc_keymap and x_layouts:
        log.debug("Keyboard layouts and virtual console keymap already set - nothing to do")
        return x_layouts, vc_keymap

    live_keyboard = get_live_keyboard_instance()
    # layouts are not set by user, we should take a look for live configuration if available
    if not x_layouts and live_keyboard:
        log.debug("Keyboard configuration from Live system is available")
        x_layouts = live_keyboard.read_keyboard_layouts()

    if not vc_keymap and not x_layouts:
        log.debug("Using default value %s for missing virtual console keymap", DEFAULT_KEYBOARD)
        vc_keymap = DEFAULT_KEYBOARD

    if not vc_keymap or not x_layouts:
        x_layouts, vc_keymap = _resolve_missing_by_conversion(localed_wrapper, x_layouts, vc_keymap)

    return x_layouts, vc_keymap


def _resolve_missing_by_conversion(localed_wrapper, x_layouts, vc_keymap):
    if not vc_keymap:
        vc_keymap = localed_wrapper.convert_layouts(x_layouts)
        log.debug("Missing virtual console keymap value %s converted from %s X layouts",
                  vc_keymap, x_layouts)
    if not x_layouts:
        x_layouts = localed_wrapper.convert_keymap(vc_keymap)
        log.debug("Missing X layouts value %s converted from %s virtual console keymap",
                  x_layouts, vc_keymap)

    return x_layouts, vc_keymap
