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
from pyanaconda import safe_dbus
from pyanaconda.core.glib import GError, Variant
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.keyboard import join_layout_variant, parse_layout_variant

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

LOCALED_SERVICE = "org.freedesktop.locale1"
LOCALED_OBJECT_PATH = "/org/freedesktop/locale1"
LOCALED_IFACE = "org.freedesktop.locale1"


class LocaledWrapper(object):
    """
    Class wrapping systemd-localed daemon functionality. By using safe_dbus
    module it tries to prevent failures related to threads and main loops.
    """

    def __init__(self):
        try:
            self._connection = safe_dbus.get_new_system_connection()
        except GError as e:
            if conf.system.provides_system_bus:
                raise

            log.error("Failed to get safe_dbus connection: %s", e)
            self._connection = None

    @property
    def keymap(self):
        try:
            keymap = safe_dbus.get_property_sync(LOCALED_SERVICE,
                                                 LOCALED_OBJECT_PATH,
                                                 LOCALED_IFACE,
                                                 "VConsoleKeymap",
                                                 self._connection)
        except (safe_dbus.DBusPropertyError, safe_dbus.DBusCallError):
            # no value for the property
            log.error("Failed to get the value for the systemd-localed's "
                      "VConsoleKeymap property")
            return ""

        # returned GVariant is unpacked to a tuple with a single element
        return keymap[0]

    @property
    def layouts_variants(self):
        try:
            layouts = safe_dbus.get_property_sync(LOCALED_SERVICE,
                                                  LOCALED_OBJECT_PATH,
                                                  LOCALED_IFACE,
                                                  "X11Layout",
                                                  self._connection)
        except (safe_dbus.DBusPropertyError, safe_dbus.DBusCallError):
            # no value for the property
            log.error("Failed to get the value for the systemd-localed's "
                      "X11Layout property")
            return [""]

        try:
            variants = safe_dbus.get_property_sync(LOCALED_SERVICE,
                                                   LOCALED_OBJECT_PATH,
                                                   LOCALED_IFACE,
                                                   "X11Variant",
                                                   self._connection)
        except (safe_dbus.DBusPropertyError, safe_dbus.DBusCallError):
            # no value for the property
            log.error("Failed to get the value for the systemd-localed's "
                      "X11Variant property")
            variants = []

        # returned GVariants are unpacked to tuples with single elements
        # containing comma-separated values
        layouts = layouts[0].split(",")

        if variants:
            variants = variants[0].split(",")

        # if there are more layouts than variants, empty strings should be appended
        diff = len(layouts) - len(variants)
        variants.extend(diff * [""])
        return [join_layout_variant(layout, variant) for layout, variant in zip(layouts, variants)]

    @property
    def options(self):
        try:
            options = safe_dbus.get_property_sync(LOCALED_SERVICE,
                                                  LOCALED_OBJECT_PATH,
                                                  LOCALED_IFACE,
                                                  "X11Options",
                                                  self._connection)
        except (safe_dbus.DBusPropertyError, safe_dbus.DBusCallError):
            # no value for the property
            log.error("Failed to get the value for the systemd-localed's "
                      "X11Options property")
            return ""

        # returned GVariant is unpacked to a tuple with a single element
        return options[0]

    def set_keymap(self, keymap, convert=False):
        """
        Method that sets VConsole keymap via systemd-localed's DBus API.

        :param keymap: VConsole keymap that should be set
        :type keymap: str
        :param convert: whether the keymap should be converted to a X11 layout
                        (see set_and_convert_keymap)
        :type convert: bool
        """

        # args: keymap, keymap_toggle, convert, user_interaction
        # where convert indicates whether the keymap should be converted
        # to X11 layout and user_interaction indicates whether PolicyKit
        # should ask for credentials or not
        args = Variant('(ssbb)', (keymap, "", convert, False))

        try:
            safe_dbus.call_sync(LOCALED_SERVICE, LOCALED_OBJECT_PATH, LOCALED_IFACE,
                                "SetVConsoleKeyboard", args, self._connection)
        except safe_dbus.DBusCallError as e:
            log.error("Failed to set keymap: %s", e)

    def convert_keymap(self, keymap):
        """
        Method that returns X11 layouts and variants that (systemd-localed
        thinks) match given keymap best.

        :param keymap: VConsole keymap
        :type keymap: str
        :return: X11 layouts and variants that (systemd-localed thinks) match
                 given keymap best
        :rtype: a list of strings
        """

        # hack around systemd's lack of functionality -- no function to just
        # convert without changing keyboard configuration
        orig_keymap = self.keymap
        ret = self.set_and_convert_keymap(keymap)
        self.set_keymap(orig_keymap)

        return ret

    def set_and_convert_keymap(self, keymap):
        """
        Method that sets VConsole keymap and returns X11 layouts and
        variants that (systemd-localed thinks) match given keymap best.

        :return: a list of "layout (variant)" or "layout" layout specifications
        :rtype: a list of strings
        """
        self.set_keymap(keymap, convert=True)
        return list(self.layouts_variants)

    def set_layouts(self, layouts_variants, options=None, convert=False):
        """
        Method that sets X11 layouts and variants (for later X sessions) via
        systemd-localed's DBus API.

        :param layout_variant: list of 'layout (variant)' or 'layout'
                               specifications of layouts and variants
        :type layout_variant: list of strings
        :param options: list of X11 options that should be set
        :type options: list of strings
        :param convert: whether the keymap should be converted to a X11 layout
                        (see set_and_convert_keymap)
        :type convert: bool
        """

        layouts = []
        variants = []

        for layout_variant in (nonempty for nonempty in layouts_variants
                               if nonempty):
            (layout, variant) = parse_layout_variant(layout_variant)
            layouts.append(layout)
            variants.append(variant)

        layouts_str = ",".join(layouts)
        variants_str = ",".join(variants)
        if options:
            opts_str = ",".join(options)
        else:
            opts_str = ""

        # args: layout, model, variant, options, convert, user_interaction
        # where convert indicates whether the keymap should be converted
        # to X11 layout and user_interaction indicates whether PolicyKit
        # should ask for credentials or not
        args = Variant("(ssssbb)", (layouts_str, "", variants_str, opts_str,
                                    convert, False))
        try:
            safe_dbus.call_sync(LOCALED_SERVICE, LOCALED_OBJECT_PATH, LOCALED_IFACE,
                                "SetX11Keyboard", args, self._connection)
        except safe_dbus.DBusCallError as e:
            log.error("Failed to set layouts: %s", e)

    def set_and_convert_layouts(self, layouts_variants):
        """
        Method that sets X11 layout and variant (for later X sessions)
        and returns VConsole keymap that (systemd-localed thinks) matches
        given layout and variant best.

        :return: a keymap matching layout and variant best
        :rtype: string
        """

        self.set_layouts(layouts_variants, convert=True)

        return self.keymap

    def convert_layouts(self, layouts_variants):
        """
        Method that returns VConsole keymap that (systemd-localed thinks)
        matches given layout and variant best.

        :param layout_variant: 'layout (variant)' or 'layout' specification
        :type layout_variant: str
        :return: a keymap matching layout and variant best
        :rtype: string
        """

        # hack around systemd's lack of functionality -- no function to just
        # convert without changing keyboard configuration
        orig_layouts_variants = self.layouts_variants
        ret = self.set_and_convert_layouts(layouts_variants)
        self.set_layouts(orig_layouts_variants)

        return ret
