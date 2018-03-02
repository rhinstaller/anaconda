#
# DBus interface for the localization module.
#
# Copyright (C) 2018 Red Hat, Inc.
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

from pyanaconda.dbus.constants import MODULE_LOCALIZATION_NAME
from pyanaconda.dbus.property import emits_properties_changed
from pyanaconda.dbus.typing import *  # pylint: disable=wildcard-import
from pyanaconda.modules.common.base import KickstartModuleInterface
from pyanaconda.dbus.interface import dbus_interface


@dbus_interface(MODULE_LOCALIZATION_NAME)
class LocalizationInterface(KickstartModuleInterface):
    """DBus interface for Localization module."""

    def connect_signals(self):
        super().connect_signals()
        self.implementation.language_changed.connect(self.changed("Language"))
        self.implementation.language_support_changed.connect(self.changed("LanguageSupport"))
        self.implementation.keyboard_changed.connect(self.changed("Keyboard"))
        self.implementation.vc_keymap_changed.connect(self.changed("VirtualConsoleKeymap"))
        self.implementation.x_layouts_changed.connect(self.changed("XLayouts"))
        self.implementation.switch_options_changed.connect(self.changed("LayoutSwitchOptions"))

    @property
    def Language(self) -> Str:
        """The language the system will use."""
        return self.implementation.language

    @emits_properties_changed
    def SetLanguage(self, language: Str):
        """Set the language.

        Sets the language to use during installation and the default language
        to use on the installed system.

        The value (language ID) can be the same as any recognized setting for
        the ``$LANG`` environment variable, though not all languages are
        supported during installation.

        :param language: Language ID ($LANG).
        """
        self.implementation.set_language(language)

    @property
    def LanguageSupport(self) -> List[Str]:
        """Supported languages on the system."""
        return self.implementation.language_support

    @emits_properties_changed
    def SetLanguageSupport(self, language_support: List[Str]):
        """Set the languages for which the support should be installed.

        Language support packages for specified languages will be installed.

        :param language_support: IDs of languages ($LANG) to be supported on system.
        """
        self.implementation.set_language_support(language_support)

    # TODO MOD - remove this when we get logic for inferring what we are
    # getting and the other option value (localed proxy) into the module?
    @property
    def Keyboard(self) -> Str:
        """Generic system keyboard specification."""
        return self.implementation.keyboard

    @emits_properties_changed
    def SetKeyboard(self, keyboard: Str):
        """Set the system keyboard type in generic way.

        Can contain virtual console keyboard mapping or X layout specification.
        This is deprecated way of specifying keyboard, use either
        SetVirtualConsoleKeymap and/or SetXLayouts.

        :param keyboard: system keyboard specification
        """
        self.implementation.set_keyboard(keyboard)

    @property
    def VirtualConsoleKeymap(self) -> Str:
        """Virtual Console keyboard mapping."""
        return self.implementation.vc_keymap

    @emits_properties_changed
    def SetVirtualConsoleKeymap(self, vc_keymap: Str):
        """Set Virtual console keyboard mapping.

        The mapping name corresponds to filenames in /usr/lib/kbd/keymaps
        (localectl --list-keymaps).

        :param vc_keymap: Virtual console keymap name.
        """
        self.implementation.set_vc_keymap(vc_keymap)

    @property
    def XLayouts(self) -> List[Str]:
        """X Layouts that should be used on the system."""
        return self.implementation.x_layouts

    @emits_properties_changed
    def SetXLayouts(self, x_layouts: List[Str]):
        """Set the X layouts for the system.

        The layout is specified by values used by setxkbmap(1).  Accepts either
        layout format (eg "cz") or the layout(variant) format (eg "cz (qerty)")

        :param x_layouts: List of x layout specifications.
        """
        self.implementation.set_x_layouts(x_layouts)

    @property
    def LayoutSwitchOptions(self) -> List[Str]:
        """List of options for layout switching"""
        return self.implementation.switch_options

    @emits_properties_changed
    def SetLayoutSwitchOptions(self, switch_options: List[Str]):
        """Set the layout switchin options.

        Accepts the same values as setxkbmap(1) for switching.

        :param options: List of layout switching options.
        """
        self.implementation.set_switch_options(switch_options)
