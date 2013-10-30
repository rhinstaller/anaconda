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
This module include functions and classes for dealing with multiple layouts in
Anaconda. It wraps the libxklavier functionality to protect Anaconda from
dealing with its "nice" API that looks like a Lisp-influenced "good old C" and
also systemd-localed functionality.

It provides a XklWrapper class with several methods that can be used for listing
and various modifications of keyboard layouts settings and LocaledWrapper class
with methods for setting, getting and mutually converting X layouts and VConsole
keymaps.

"""

import types
import os
import re
import shutil
import ctypes
import gettext
import threading

from collections import namedtuple

from pyanaconda import iutil
from pyanaconda import flags
from pyanaconda.safe_dbus import dbus_call_safe_sync, dbus_get_property_safe_sync
from pyanaconda.safe_dbus import DBUS_SYSTEM_BUS_ADDR, DBusPropertyError
from pyanaconda.constants import DEFAULT_VC_FONT, DEFAULT_KEYBOARD, THREAD_XKL_WRAPPER_INIT
from pyanaconda.threads import threadMgr, AnacondaThread

from gi.repository import Xkl, Gio, GLib

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

# namedtuple for information about a keyboard layout (its language and description)
LayoutInfo = namedtuple("LayoutInfo", ["lang", "desc"])

Xkb_ = lambda x: gettext.ldgettext("xkeyboard-config", x)
iso_ = lambda x: gettext.ldgettext("iso_639", x)

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

def _join_layout_variant(layout, variant=""):
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
    return _join_layout_variant(layout, variant)

def populate_missing_items(keyboard):
    """
    Function that populates keyboard.vc_keymap and keyboard.x_layouts if
    they are missing. By invoking LocaledWrapper's methods this function
    MODIFIES CONFIGURATION FILES.

    :type keyboard: ksdata.keyboard object

    """

    localed = LocaledWrapper()

    if keyboard.x_layouts and not keyboard.vc_keymap:
        keyboard.vc_keymap = localed.set_and_convert_layout(keyboard.x_layouts[0])

    if not keyboard.vc_keymap:
        keyboard.vc_keymap = DEFAULT_KEYBOARD

    if not keyboard.x_layouts:
        c_lay_var = localed.set_and_convert_keymap(keyboard.vc_keymap)
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

def dracut_setup_args(keyboard):
    """
    Function returning dracut setup args for the given keyboard configuration.

    :type keyboard: ksdata.keyboard object

    """

    if not keyboard.vc_keymap:
        populate_missing_items(keyboard)

    args = set()
    args.add("vconsole.keymap=%s" % keyboard.vc_keymap)
    args.add("vconsole.font=%s" % DEFAULT_VC_FONT)

    return args

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
    c_lay_var = ""
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
            c_lay_var = localed.set_and_convert_keymap(keyboard.vc_keymap)

    if not keyboard.x_layouts:
        if c_lay_var:
            # suggested by systemd-localed for a requested VConsole keymap
            keyboard.x_layouts.append(c_lay_var)
        if keyboard.vc_keymap:
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

def background_XklWrapper_initialize():
    """
    Create the XklWrapper singleton instance in a separate thread to save time
    when it's really needed.

    """

    threadMgr.add(AnacondaThread(name=THREAD_XKL_WRAPPER_INIT, target=XklWrapper.get_instance))

def item_str(s):
    """Convert a zero-terminated byte array to a proper str"""

    # depending of version of libxklavier and the tools generating introspection
    # data the value of 's' can be either byte string or list of integers
    if type(s) == types.StringType:
        i = s.find(b'\x00')
        s = s[:i]
    elif type(s) == types.ListType:
        # XXX: this is the wrong case that should be fixed (rhbz#920595)
        i = s.index(0)
        s = "".join(chr(ctypes.c_uint8(char).value) for char in s[:i])

    return s.decode("utf-8") #there are some non-ascii layout descriptions

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
        from gi.repository import GdkX11

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
                lay_var_str = ",".join(map(_join_layout_variant,
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
            name = item_str(item.name) + " (" + item_str(subitem.name) + ")"
            description = item_str(subitem.description)
        else:
            name = item_str(item.name)
            description = item_str(item.description)

        #if this layout has already been added for some other language,
        #do not add it again (would result in duplicates in our lists)
        if name not in self._layout_infos:
            self._layout_infos[name] = LayoutInfo(lang.encode("utf-8"),
                                                  description.encode("utf-8"))

    def _get_country_variant(self, c_reg, item, subitem, country):
        if subitem:
            name = item_str(item.name) + " (" + item_str(subitem.name) + ")"
            description = item_str(subitem.description)
        else:
            name = item_str(item.name)
            description = item_str(item.description)

        # if the layout was not added with any language, add it with a country
        if name not in self._layout_infos:
            self._layout_infos[name] = LayoutInfo(country.encode("utf-8"),
                                                  description.encode("utf-8"))

    def _get_language_variants(self, c_reg, item, user_data=None):
        lang_name, lang_desc = item_str(item.name), item_str(item.description)

        c_reg.foreach_language_variant(lang_name, self._get_lang_variant, lang_desc)

    def _get_country_variants(self, c_reg, item, user_data=None):
        country_name, country_desc = item_str(item.name), item_str(item.description)

        c_reg.foreach_country_variant(country_name, self._get_country_variant,
                                      country_desc)

    def _get_switch_option(self, c_reg, item, user_data=None):
        """Helper function storing layout switching options in foreach cycle"""
        desc = item_str(item.description)
        name = item_str(item.name)

        self._switch_opt_infos[name] = desc.encode("utf-8")

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

        return _join_layout_variant(layout, variant)

    def get_available_layouts(self):
        """A generator yielding layouts (no need to store them as a bunch)"""

        return self._layout_infos.iterkeys()

    def get_switching_options(self):
        """Method returning list of available layout switching options"""

        return self._switch_opt_infos.iterkeys()

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
        if xlated:
            description = Xkb_(layout_info.desc).decode("utf-8")
        else:
            description = layout_info.desc

        if with_lang and layout_info.lang:
            # translate language and upcase its first letter, translate the
            # layout-variant description
            if xlated:
                lang = iso_(layout_info.lang).decode("utf-8")
            else:
                lang = layout_info.lang

            return "%s (%s)" % (iutil.upcase_first_letter(lang), description)
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

    def activate_default_layout(self):
        """
        Activates default layout (the first one in the list of configured
        layouts).

        """

        self._engine.lock_group(0)

    def is_valid_layout(self, layout):
        """Return if given layout is valid layout or not"""

        return layout in self._layout_infos

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

class LocaledWrapperError(KeyboardConfigError):
    """Exception class for reporting Localed-related problems"""
    pass

class LocaledWrapper(object):
    """
    Class wrapping systemd-localed daemon functionality. By using safe_dbus
    module it tries to prevent failures related to threads and main loops.

    """

    def __init__(self):
        self._connection = Gio.DBusConnection.new_for_address_sync(
                             DBUS_SYSTEM_BUS_ADDR,
                             Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT|
                             Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
                             None, None)

    @property
    def keymap(self):
        try:
            keymap = dbus_get_property_safe_sync(LOCALED_SERVICE,
                                                 LOCALED_OBJECT_PATH,
                                                 LOCALED_IFACE,
                                                 "VConsoleKeymap",
                                                 self._connection)
        except DBusPropertyError:
            # no value for the property
            log.error("Failed to get the value for the systemd-localed's "
                      "VConsoleKeymap property")
            return ""

        # returned GVariant is unpacked to a tuple with a single element
        return keymap[0]

    @property
    def layouts_variants(self):
        try:
            layouts = dbus_get_property_safe_sync(LOCALED_SERVICE,
                                                  LOCALED_OBJECT_PATH,
                                                  LOCALED_IFACE,
                                                  "X11Layout",
                                                  self._connection)
        except DBusPropertyError:
            # no value for the property
            log.error("Failed to get the value for the systemd-localed's "
                      "X11Layout property")
            return [""]

        try:
            variants = dbus_get_property_safe_sync(LOCALED_SERVICE,
                                                   LOCALED_OBJECT_PATH,
                                                   LOCALED_IFACE,
                                                   "X11Variant",
                                                   self._connection)
        except DBusPropertyError:
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

        # map can be used with multiple lists and works like zipWith (Haskell)
        return map(_join_layout_variant, layouts, variants)

    @property
    def options(self):
        try:
            options = dbus_get_property_safe_sync(LOCALED_SERVICE,
                                                  LOCALED_OBJECT_PATH,
                                                  LOCALED_IFACE,
                                                  "X11Options",
                                                  self._connection)
        except DBusPropertyError:
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

        dbus_call_safe_sync(LOCALED_SERVICE, LOCALED_OBJECT_PATH, LOCALED_IFACE,
                            "SetVConsoleKeyboard", args, self._connection)

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

        for layout_variant in layouts_variants:
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
        dbus_call_safe_sync(LOCALED_SERVICE, LOCALED_OBJECT_PATH, LOCALED_IFACE,
                            "SetX11Keyboard", args, self._connection)

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
