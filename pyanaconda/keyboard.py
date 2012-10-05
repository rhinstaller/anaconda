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
This module include functions and classes for dealing with multiple layouts
in Anaconda. It wraps the libxklavier functionality to protect Anaconda
from dealing with its "nice" API that looks like a Lisp-influenced
"good old C".

It provides a XklWrapper class with several methods that can be used
for listing and various modifications of keyboard layouts settings.

"""

import os
import re
from pyanaconda import iutil

from gi.repository import Xkl

import logging
log = logging.getLogger("anaconda")

class KeyboardConfigError(Exception):
    """Exception class for keyboard configuration related problems"""

    pass

def _parse_layout_variant(layout):
    """
    Parse layout and variant from the string that may look like 'layout' or
    'layout (variant)'.

    @return: the (layout, variant) pair, where variant can be ""
    @rtype: tuple

    """

    variant = ""

    lbracket_idx = layout.find("(")
    rbracket_idx = layout.rfind(")")
    if lbracket_idx != -1:
        variant = layout[(lbracket_idx + 1) : rbracket_idx]
        layout = layout[:lbracket_idx].strip()

    return (layout, variant)

def get_layouts_xorg_conf(keyboard):
    """
    Get the xorg.conf content setting up layouts in the ksdata.

    @param keyboard: ksdata.keyboard object
    @rtype: str

    """

    layouts = list()
    variants = list()

    for layout_variant in keyboard.layouts_list:
        (layout, variant) = _parse_layout_variant(layout_variant)
        layouts.append(layout)
        variants.append(variant)

    #section header
    ret = 'Section "InputClass"\n'\
          '\tIdentifier\t"kickstart"\n'\
          '\tMatchIsKeyboard\t"on"\n'

    #layouts
    ret += '\tOption\t"XkbLayout"\t'
    ret += '"' + ','.join(layouts) + '"\n'

    #variants
    ret += '\tOption\t"XkbVariant"\t'
    ret += '"' + ','.join(variants) + '"\n'

    #switching
    #TODO: add option for switching combination
    #for now, let's default to Alt+Shift
    ret += '\tOption\t"XkbOptions"\t'
    ret += '"grp:alt_shift_toggle"\n'

    #section footer
    ret += 'EndSection'

    return ret

def write_layouts_config(keyboard, root):
    """
    Function that writes files with layouts configuration to
    $root/etc/X11/xorg.conf.d/01-anaconda-layouts.conf and
    $root/etc/sysconfig/keyboard.

    @param keyboard: ksdata.keyboard object
    @param root: path to the root of the installed system

    """

    xconf_dir = os.path.normpath(root + "/etc/X11/xorg.conf.d")
    xconf_file = "01-anaconda-keyboard.conf"

    sysconf_dir = os.path.normpath(root + "/etc/sysconfig")
    sysconf_file = "keyboard"

    try:
        if not os.path.isdir(xconf_dir):
            os.makedirs(xconf_dir)

    except OSError as oserr:
        raise KeyboardConfigError("Cannot create directory xorg.conf.d")

    try:
        with open(os.path.join(xconf_dir, xconf_file), "w") as fobj:
            fobj.write(get_layouts_xorg_conf(keyboard))

        with open(os.path.join(sysconf_dir, sysconf_file), "w") as fobj:
            fobj.write('vconsole.keymap="%s"\n' % keyboard.keyboard)

    except IOError as ioerr:
        raise KeyboardConfigError("Cannot write keyboard configuration files")

def activate_console_keymap(keymap):
    """
    Try to setup a given keymap as a console keymap. If there is no such
    keymap, try to setup a basic variant (e.g. 'cz' instead of 'cz (qwerty)').

    @param keymap: a keymap
    @type keymap: string
    @raise KeyboardConfigError: if loadkeys command is not available
    @return: False if failed to activate both the given keymap and its basic
             variant, True otherwise

    """

    try:
        #TODO: replace with calling systemd-localed methods once it can load
        #      X layouts
        ret = iutil.execWithRedirect("loadkeys", [keymap], stdout="/dev/tty5",
                                     stderr="/dev/tty5")
    except OSError as oserr:
        msg = "'loadkeys' command not available (%s)" % oserr.strerror
        raise KeyboardConfigError(msg)

    if ret != 0:
        log.error("Failed to activate keymap %s" % keymap)

        #failed to activate the given keymap, extract and try
        #the basic keymap -- e.g. 'cz-cp1250' -> 'cz'
        parts = re.split(r'[- _(]', keymap, 1)
        if len(parts) == 0:
            log.error("Failed to extract basic keymap from: %s" % keymap)
            return False

        keymap = parts[0]

        ret = iutil.execWithRedirect("loadkeys", [keymap], stdout="/dev/tty5",
                                     stderr="/dev/tty5")

        if ret != 0:
            log.error("Failed to activate basic variant %s" % keymap)
        else:
            log.error("Activated basic variant %s, instead" % keymap)

    return ret == 0

def item_str(s):
    """Convert a zero-terminated byte array to a proper str"""

    i = s.find(b'\x00')
    return s[:i].decode("utf-8") #there are some non-ascii layout descriptions

class _Layout(object):
    """Internal class representing a single layout variant"""

    def __init__(self, name, desc):
        self.name = name
        self.desc = desc

    def __str__(self):
        return '%s (%s)' % (self.name, self.desc)

    @property
    def description(self):
        return self.desc

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

    @staticmethod
    def get_instance():
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
        if diff > 0:
            self._rec.set_variants(self._rec.variants + (diff * [""]))
            if not self._rec.activate(self._engine):
                raise XklWrapperError("Failed to initialize layouts")

        #initialize layout switching to Alt+Shift
        self._rec.set_options(self._rec.options + ["grp:alt_shift_toggle"])
        if not self._rec.activate(self._engine):
            raise XklWrapperError("Cannot initialize layout switching")

        #needed also for Gkbd.KeyboardDrawingDialog
        self.configreg = Xkl.ConfigRegistry.get_instance(self._engine)
        self.configreg.load(False)

        self._language_keyboard_variants = dict()
        self._country_keyboard_variants = dict()

        #we want to display layouts as 'language (description)'
        self.name_to_show_str = dict()

        #this might take quite a long time
        self.configreg.foreach_language(self._get_language_variants, None)

    def _get_variant(self, c_reg, item, subitem, dest):
        if subitem:
            name = item_str(item.name) + " (" + item_str(subitem.name) + ")"
            description = item_str(subitem.description)
        else:
            name = item_str(item.name)
            description = item_str(item.description)

        self.name_to_show_str[name] = "%s (%s)" % (dest.encode("utf-8"), description.encode("utf-8"))
        self._variants_list.append(_Layout(name, description))

    def _get_language_variants(self, c_reg, item, user_data=None):
        #helper "global" variable
        self._variants_list = list()
        lang_name, lang_desc = item_str(item.name), item_str(item.description)

        c_reg.foreach_language_variant(lang_name, self._get_variant, lang_desc)

        self._language_keyboard_variants[lang_desc] = self._variants_list

    def _get_country_variants(self, c_reg, item, user_data=None):
        #helper "global" variable
        self._variants_list = list()
        country_name, country_desc = item_str(item.name), item_str(item.description)

        c_reg.foreach_country_variant(country_name, self._get_variant, None)

        self._country_keyboard_variants[(country_name, country_desc)] = self._variants_list

    def get_available_layouts(self):
        """A generator yielding layouts (no need to store them as a bunch)"""

        for lang_desc, variants in sorted(self._language_keyboard_variants.items()):
            for layout in variants:
                yield layout.name

    def get_default_language_layout(self, language):
        """Get the default layout for a given language"""

        language_layouts = self._language_keyboard_variants.get(language, None)

        if not language_layouts:
            return None

        #first layout (should exist for every language)
        return language_layouts[0].name

    def get_current_layout_name(self):
        """
        Get current activated X layout's name

        @return: current activated X layout's name (e.g. "Czech (qwerty)")

        """

        self._engine.start_listen(Xkl.EngineListenModes.TRACK_KEYBOARD_STATE)
        state = self._engine.get_current_state()
        groups_names = self._engine.get_groups_names()
        self._engine.stop_listen(Xkl.EngineListenModes.TRACK_KEYBOARD_STATE)

        return groups_names[state.group]

    def add_layout(self, layout):
        """
        Method that tries to add a given layout to the current X configuration.

        The X layouts configuration is handled by two lists. A list of layouts
        and a list of variants. Index-matching items in these lists (as if they
        were zipped) are used for the construction of real layouts (e.g.
        'cz (qwerty)').

        @param layout: either 'layout' or 'layout (variant)'
        @raise XklWrapperError: if the given layout cannot be added

        """

        #we can get 'layout' or 'layout (variant)'
        (layout, variant) = _parse_layout_variant(layout)

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

        @param layout: either 'layout' or 'layout (variant)'
        @raise XklWrapperError: if the given layout cannot be removed

        """

        #we can get 'layout' or 'layout (variant)'
        (layout, variant) = _parse_layout_variant(layout)

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

        @param layouts_list: list of layouts defined as either 'layout' or
                             'layout (variant)'
        @raise XklWrapperError: if layouts cannot be replaced with the new ones

        """

        new_layouts = list()
        new_variants = list()

        for layout_variant in layouts_list:
            (layout, variant) = _parse_layout_variant(layout_variant)
            new_layouts.append(layout)
            new_variants.append(variant)

        self._rec.set_layouts(new_layouts)
        self._rec.set_variants(new_variants)

        if not self._rec.activate(self._engine):
            msg = "Failed to replace layouts with: %s" % ",".join(layouts_list)
            raise XklWrapperError(msg)
