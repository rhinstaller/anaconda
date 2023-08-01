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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from pyanaconda.core.constants import DEFAULT_KEYBOARD

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


def get_missing_keyboard_configuration(localed_wrapper, x_layouts, vc_keymap):
    """Get missing keyboard settings by conversion and default values.

    :param localed_wrapper: instance of systemd-localed service wrapper
    :type localed_wrapper: LocaledWrapper
    :param x_layouts: list of X layout specifications
    :type x_layouts: list(str)
    :param vc_keymap: virtual console keyboard mapping name
    :type vc_keymap: str
    :returns: tuple of X layouts and VC keyboard settings
    :rtype: (list(str), str))
    """
    if not vc_keymap and not x_layouts:
        log.debug("Using default value %s for missing virtual console keymap", DEFAULT_KEYBOARD)
        vc_keymap = DEFAULT_KEYBOARD

    if not vc_keymap:
        vc_keymap = localed_wrapper.convert_layouts(x_layouts)
        log.debug("Missing virtual console keymap value %s converted from %s X layouts",
                  vc_keymap, x_layouts)
    if not x_layouts:
        x_layouts = localed_wrapper.convert_keymap(vc_keymap)
        log.debug("Missing X layouts value %s converted from %s virtual console keymap",
                  x_layouts, vc_keymap)

    return x_layouts, vc_keymap
