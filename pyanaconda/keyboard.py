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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Martin Gracik <mgracik@redhat.com>
#                    Vratislav Podzimek <vpodzime@redhat.com>
#

"""
This module provides functions for dealing with keyboard layouts/keymaps in
Anaconda and the LocaledWrapper class with methods for setting, getting and
mutually converting X layouts and VConsole keymaps.

"""

import os
import re
import shutil

from pyanaconda import iutil
from pyanaconda import safe_dbus
from pyanaconda.constants import DEFAULT_VC_FONT, DEFAULT_KEYBOARD
from pyanaconda.flags import can_touch_runtime_system

from gi.repository import GLib

import logging
log = logging.getLogger("anaconda")

LOCALED_SERVICE = "org.freedesktop.locale1"
LOCALED_OBJECT_PATH = "/org/freedesktop/locale1"
LOCALED_IFACE = "org.freedesktop.locale1"

# should match and parse strings like 'cz' or 'cz (qwerty)' regardless of white
# space
LAYOUT_VARIANT_RE = re.compile(r'^\s*(\w+)\s*' # layout plus
                               r'(?:(?:\(\s*([-\w]+)\s*\))' # variant in parentheses
                               r'|(?:$))\s*') # or nothing

class KeyboardConfigError(Exception):
    """Exception class for keyboard configuration related problems"""

    pass

class InvalidLayoutVariantSpec(Exception):
    """
    Exception class for errors related to parsing layout and variant specification strings.

    """

    pass

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

def populate_missing_items(keyboard):
    """
    Function that populates keyboard.vc_keymap and keyboard.x_layouts if they
    are missing. By invoking LocaledWrapper's methods this function READS AND
    WRITES CONFIGURATION FILES (but tries to keep their content unchanged).

    :type keyboard: ksdata.keyboard object

    """

    localed = LocaledWrapper()

    if keyboard._keyboard and not (keyboard.vc_keymap or keyboard.x_layouts):
        # we were given just a value in the old format, use it as a vc_keymap
        keyboard.vc_keymap = keyboard._keyboard

    if keyboard.x_layouts and not keyboard.vc_keymap:
        keyboard.vc_keymap = localed.convert_layout(keyboard.x_layouts[0])

    if not keyboard.vc_keymap:
        keyboard.vc_keymap = DEFAULT_KEYBOARD

    if not keyboard.x_layouts:
        c_lay_var = localed.convert_keymap(keyboard.vc_keymap)
        keyboard.x_layouts.append(c_lay_var)

def write_keyboard_config(keyboard, root, convert=True):
    """
    Function that writes files with layouts configuration to
    $root/etc/X11/xorg.conf.d/01-anaconda-layouts.conf and
    $root/etc/vconsole.conf.

    :param keyboard: ksdata.keyboard object
    :param root: path to the root of the installed system
    :param convert: whether to convert specified values to get the missing
                    ones
    :param weight: weight (prefix) of the xorg.conf file written out

    """

    if convert:
        populate_missing_items(keyboard)

    xconf_dir = "/etc/X11/xorg.conf.d"
    xconf_file = "00-keyboard.conf"
    xconf_file_path = os.path.normpath(xconf_dir + "/" + xconf_file)

    vcconf_dir = os.path.normpath(root + "/etc")
    vcconf_file = "vconsole.conf"

    errors = []

    try:
        if not os.path.isdir(xconf_dir):
            os.makedirs(xconf_dir)

    except OSError:
        errors.append("Cannot create directory xorg.conf.d")

    if keyboard.x_layouts:
        localed_wrapper = LocaledWrapper()

        if root != "/":
            # writing to a different root, we need to save these values, so that
            # we can restore them when we have the file written out
            layouts_variants = localed_wrapper.layouts_variants
            options = localed_wrapper.options

            # set systemd-localed's layouts, variants and switch options, which
            # also generates a new conf file
            localed_wrapper.set_layouts(keyboard.x_layouts,
                                        keyboard.switch_options)

            # make sure the right directory exists under the given root
            rooted_xconf_dir = os.path.normpath(root + "/" + xconf_dir)
            try:
                if not os.path.isdir(rooted_xconf_dir):
                    os.makedirs(rooted_xconf_dir)
            except OSError:
                errors.append("Cannot create directory xorg.conf.d")

            # copy the file to the chroot
            try:
                shutil.copy2(xconf_file_path,
                             os.path.normpath(root + "/" + xconf_file_path))
            except IOError:
                # The file may not exist (eg. text install) so don't raise
                pass

            # restore the original values
            localed_wrapper.set_layouts(layouts_variants,
                                        options)
        else:
            try:
                # just let systemd-localed write out the conf file
                localed_wrapper.set_layouts(keyboard.x_layouts,
                                            keyboard.switch_options)
            except InvalidLayoutVariantSpec as ilvs:
                # some weird value appeared as a requested X layout
                log.error("Failed to write out config file: %s", ilvs)

                # try default
                keyboard.x_layouts = [DEFAULT_KEYBOARD]
                localed_wrapper.set_layouts(keyboard.x_layouts,
                                            keyboard.switch_options)

    if keyboard.vc_keymap:
        try:
            with open(os.path.join(vcconf_dir, vcconf_file), "w") as fobj:
                fobj.write('KEYMAP="%s"\n' % keyboard.vc_keymap)

                # systemd now defaults to a font that cannot display non-ascii
                # characters, so we have to tell it to use a better one
                fobj.write('FONT="%s"\n' % DEFAULT_VC_FONT)
        except IOError:
            errors.append("Cannot write vconsole configuration file")

    if errors:
        raise KeyboardConfigError("\n".join(errors))

def _try_to_load_keymap(keymap):
    """
    Method that tries to load keymap and returns boolean indicating if it was
    successfull or not. It can be used to test if given string is VConsole
    keymap or not, but in case it is given valid keymap, IT REALLY LOADS IT!.

    :type keymap: string
    :raise KeyboardConfigError: if loadkeys command is not available
    :return: True if given string was a valid keymap and thus was loaded,
             False otherwise

    """

    # BUG: systemd-localed should be able to tell us if we are trying to
    #      activate invalid keymap. Then we will be able to get rid of this
    #      fuction

    ret = 0

    try:
        ret = iutil.execWithRedirect("loadkeys", [keymap])
    except OSError as oserr:
        msg = "'loadkeys' command not available (%s)" % oserr.strerror
        raise KeyboardConfigError(msg)

    return ret == 0

def activate_keyboard(keyboard):
    """
    Try to setup VConsole keymap and X11 layouts as specified in kickstart.

    :param keyboard: ksdata.keyboard object
    :type keyboard: ksdata.keyboard object

    """

    localed = LocaledWrapper()
    c_lays_vars = []
    c_keymap = ""

    if keyboard._keyboard and not (keyboard.vc_keymap or keyboard.x_layouts):
        # we were give only one value in old format of the keyboard command
        # try to guess if we were given VConsole keymap or X11 layout
        is_keymap = _try_to_load_keymap(keyboard._keyboard)

        if is_keymap:
            keyboard.vc_keymap = keyboard._keyboard
        else:
            keyboard.x_layouts.append(keyboard._keyboard)

    if keyboard.vc_keymap:
        valid_keymap = _try_to_load_keymap(keyboard.vc_keymap)
        if not valid_keymap:
            log.error("'%s' is not a valid VConsole keymap, not loading",
                        keyboard.vc_keymap)
            keyboard.vc_keymap = None
        else:
            # activate VConsole keymap and get converted layout and variant
            converted = localed.set_and_convert_keymap(keyboard.vc_keymap)

            # localed may give us multiple comma-separated layouts+variants
            c_lays_vars = converted.split(",")

    if not keyboard.x_layouts:
        if c_lays_vars:
            # suggested by systemd-localed for a requested VConsole keymap
            keyboard.x_layouts += c_lays_vars
        elif keyboard.vc_keymap:
            # nothing suggested by systemd-localed, but we may try to use the
            # same string for both VConsole keymap and X layout (will fail
            # safely if it doesn't work)
            keyboard.x_layouts.append(keyboard.vc_keymap)

    if keyboard.x_layouts:
        c_keymap = localed.set_and_convert_layout(keyboard.x_layouts[0])

        if not keyboard.vc_keymap:
            keyboard.vc_keymap = c_keymap

        # write out keyboard configuration for the X session
        write_keyboard_config(keyboard, root="/", convert=False)

class LocaledWrapperError(KeyboardConfigError):
    """Exception class for reporting Localed-related problems"""
    pass

class LocaledWrapper(object):
    """
    Class wrapping systemd-localed daemon functionality. By using safe_dbus
    module it tries to prevent failures related to threads and main loops.

    """

    def __init__(self):
        try:
            self._connection = safe_dbus.get_new_system_connection()
        except GLib.GError as e:
            if can_touch_runtime_system("raise GLib.GError", touch_live=True):
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
        args = GLib.Variant('(ssbb)', (keymap, "", convert, False))

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
        :rtype: str

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

        :return: string containing comma-separated "layout (variant)" or
                 "layout" layout specifications
        :rtype: string

        """

        self.set_keymap(keymap, convert=True)

        return ",".join(self.layouts_variants)

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
        args = GLib.Variant("(ssssbb)", (layouts_str, "", variants_str, opts_str,
                                         convert, False))
        try:
            safe_dbus.call_sync(LOCALED_SERVICE, LOCALED_OBJECT_PATH, LOCALED_IFACE,
                                "SetX11Keyboard", args, self._connection)
        except safe_dbus.DBusCallError as e:
            log.error("Failed to set layouts: %s", e)

    def set_and_convert_layout(self, layout_variant):
        """
        Method that sets X11 layout and variant (for later X sessions)
        and returns VConsole keymap that (systemd-localed thinks) matches
        given layout and variant best.

        :return: a keymap matching layout and variant best
        :rtype: string

        """

        self.set_layouts([layout_variant], convert=True)

        return self.keymap

    def convert_layout(self, layout_variant):
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
        ret = self.set_and_convert_layout(layout_variant)
        self.set_layouts(orig_layouts_variants)

        return ret

