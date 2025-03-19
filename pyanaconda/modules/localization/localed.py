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
from pyanaconda.core.dbus import SystemBus
from pyanaconda.modules.common.constants.services import LOCALED
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.keyboard import join_layout_variant, parse_layout_variant, \
    InvalidLayoutVariantSpec
from pyanaconda.core.constants import DEFAULT_KEYBOARD

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class LocaledWrapper(object):
    """Class wrapping systemd-localed daemon functionality."""

    def __init__(self):
        self._localed_proxy = None

        if not conf.system.provides_system_bus:
            log.debug("Not using localed service: "
                      "system does not provide system bus according to configuration.")
            return

        if not SystemBus.check_connection():
            log.debug("Not using localed service: "
                      "system bus connection check failed.")
            return

        self._localed_proxy = LOCALED.get_proxy()

    @property
    def keymap(self):
        """Get current VConsole keymap.

        :return: VConsole keymap specification
        :rtype: string
        """
        if not self._localed_proxy:
            return ""

        return self._localed_proxy.VConsoleKeymap

    @property
    def layouts_variants(self):
        """Get current X11 layouts with variants.

        :return: a list of "layout (variant)" or "layout" layout specifications
        :rtype: list(str)
        """
        if not self._localed_proxy:
            return []

        layouts = self._localed_proxy.X11Layout
        variants = self._localed_proxy.X11Variant

        layouts = layouts.split(",") if layouts else []
        variants = variants.split(",") if variants else []

        # if there are more layouts than variants, empty strings should be appended
        diff = len(layouts) - len(variants)
        variants.extend(diff * [""])

        return [join_layout_variant(layout, variant) for layout, variant in zip(layouts, variants)]

    @property
    def options(self):
        """Get current X11 options.

        :return: a list of X11 options
        :rtype: list(str)
        """
        if not self._localed_proxy:
            return []

        options = self._localed_proxy.X11Options

        return options.split(",") if options else []

    def set_keymap(self, keymap, convert=False):
        """Set current VConsole keymap.

        :param keymap: VConsole keymap that should be set
        :type keymap: str
        :param convert: whether the keymap should be converted and set as X11 layout
        :type convert: bool
        """
        if not self._localed_proxy:
            return ""

        self._localed_proxy.SetVConsoleKeyboard(keymap, "", convert, False)

    def convert_keymap(self, keymap):
        """Get X11 layouts and variants by converting VConsole keymap.

        NOTE: Systemd-localed performs the conversion. Current VConsole keymap
        and X11 layouts are set temporarily to the converted values in the
        process of conversion.

        :param keymap: VConsole keymap
        :type keymap: str
        :return: a list of "layout (variant)" or "layout" layout specifications
                 obtained by conversion of VConsole keymap
        :rtype: list(str)
        """
        if not self._localed_proxy:
            return []

        # hack around systemd's lack of functionality -- no function to just
        # convert without changing keyboard configuration
        orig_layouts_variants = self.layouts_variants
        orig_keymap = self.keymap
        converted_layouts = self.set_and_convert_keymap(keymap)
        self.set_layouts(orig_layouts_variants)
        self.set_keymap(orig_keymap)

        return converted_layouts

    def set_and_convert_keymap(self, keymap):
        """Set VConsole keymap and set and get converted X11 layouts.

        :param keymap: VConsole keymap
        :type keymap: str
        :return: a list of "layout (variant)" or "layout" layout specifications
                 obtained by conversion from VConsole keymap
        :rtype: list(str)
        """
        self.set_keymap(keymap, convert=True)

        return self.layouts_variants

    def set_layouts(self, layouts_variants, options=None, convert=False):
        """Set X11 layouts.

        :param layouts_variants: list of 'layout (variant)' or 'layout'
                                 specifications of layouts and variants
        :type layouts_variants: list(str)
        :param options: list of X11 options that should be set
        :type options: list(str)
        :param convert: whether the layouts should be converted to a VConsole keymap
                        (see set_and_convert_layouts)
        :type convert: bool
        """
        if not self._localed_proxy:
            return

        layouts = []
        variants = []
        parsing_failed = False

        for layout_variant in (nonempty for nonempty in layouts_variants if nonempty):
            try:
                (layout, variant) = parse_layout_variant(layout_variant)
            except InvalidLayoutVariantSpec as e:
                log.debug("Parsing of %s failed: %s", layout_variant, e)
                parsing_failed = True
                continue
            layouts.append(layout)
            variants.append(variant)

        if not layouts and parsing_failed:
            return

        layouts_str = ",".join(layouts)
        variants_str = ",".join(variants)
        options_str = ",".join(options) if options else ""

        self._localed_proxy.SetX11Keyboard(
            layouts_str,
            "",
            variants_str,
            options_str,
            convert,
            False
        )

    def set_and_convert_layouts(self, layouts_variants):
        """Set X11 layouts and set and get converted VConsole keymap.

        :param layouts_variants: list of 'layout (variant)' or 'layout'
                                 specifications of layouts and variants
        :type layouts_variants: list(str)
        :return: a VConsole keymap obtained by conversion from X11 layouts
        :rtype: str
        """

        self.set_layouts(layouts_variants, convert=True)

        return self.keymap

    def convert_layouts(self, layouts_variants):
        """Get VConsole keymap by converting X11 layouts and variants.

        NOTE: Systemd-localed performs the conversion. Current VConsole keymap
        and X11 layouts are set temporarily to the converted values in the
        process of conversion.

        :param layouts_variants: list of 'layout (variant)' or 'layout'
                                 specifications of layouts and variants
        :type layouts_variants: list(str)
        :return: a VConsole keymap obtained by conversion from X11 layouts
        :rtype: str
        """
        if not self._localed_proxy:
            return ""

        # hack around systemd's lack of functionality -- no function to just
        # convert without changing keyboard configuration
        orig_layouts_variants = self.layouts_variants
        orig_keymap = self.keymap
        ret = self.set_and_convert_layouts(layouts_variants)
        self.set_layouts(orig_layouts_variants)
        self.set_keymap(orig_keymap)

        return ret


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
        log.debug("Using default value %s for missing virtual console keymap.", DEFAULT_KEYBOARD)
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
