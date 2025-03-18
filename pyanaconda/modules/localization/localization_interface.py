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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#

from pyanaconda.modules.common.constants.services import LOCALIZATION
from dasbus.server.property import emits_properties_changed
from dasbus.typing import *  # pylint: disable=wildcard-import
from pyanaconda.modules.common.base import KickstartModuleInterface
from pyanaconda.modules.common.containers import TaskContainer
from dasbus.server.interface import dbus_interface


@dbus_interface(LOCALIZATION.interface_name)
class LocalizationInterface(KickstartModuleInterface):
    """DBus interface for Localization module."""

    def connect_signals(self):
        super().connect_signals()
        self.watch_property("Language", self.implementation.language_changed)
        self.watch_property("LanguageSupport", self.implementation.language_support_changed)
        self.watch_property("LanguageKickstarted", self.implementation.language_seen_changed)
        self.watch_property("VirtualConsoleKeymap", self.implementation.vc_keymap_changed)
        self.watch_property("XLayouts", self.implementation.x_layouts_changed)
        self.watch_property("LayoutSwitchOptions", self.implementation.switch_options_changed)
        self.watch_property("KeyboardKickstarted", self.implementation.keyboard_seen_changed)

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

    @property
    def LanguageKickstarted(self) -> Bool:
        """Was the language set in a kickstart?

        :return: True if it was set in a kickstart, otherwise False
        """
        return self.implementation.language_seen

    @emits_properties_changed
    def SetLanguageKickstarted(self, language_seen: Bool):
        """Set if language should be considered as coming from kickstart

        :param bool language_seen: if language should be considered as coming from kickstart
        """
        self.implementation.set_language_seen(language_seen)

    def SetKeyboard(self, keyboard: Str):
        """Set the system keyboard type in generic way.

        Can contain virtual console keyboard mapping or X layout specification.
        This is deprecated way of specifying keyboard, use either
        SetVirtualConsoleKeymap and/or SetXLayouts.

        :param keyboard: system keyboard specification
        """
        self.implementation.set_from_generic_keyboard_setting(keyboard)

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

    @property
    def KeyboardKickstarted(self) -> Bool:
        """Was keyboard command seen in kickstart?

        :return: True if keyboard command was seen in kickstart, otherwise False
        """
        return self.implementation.keyboard_seen

    @emits_properties_changed
    def SetKeyboardKickstarted(self, keyboard_seen: Bool):
        """Set if keyboard should be considered as coming from kickstart

        :param bool keyboard_seen: if keyboard should be considered as coming from kickstart
        """
        self.implementation.set_keyboard_seen(keyboard_seen)

    def PopulateMissingKeyboardConfigurationWithTask(self) -> ObjPath:
        """Pouplate missing keyboard configuration.

        The configuration is populated by conversion and/or default values.

        :return: DBus path of the task populating the configuration
        """
        return TaskContainer.to_object_path(
            self.implementation.populate_missing_keyboard_configuration_with_task()
        )

    def ApplyKeyboardWithTask(self) -> ObjPath:
        """Apply keyboard configuration to the current system.

        :return: DBus path of the task applying the configuration
        """
        return TaskContainer.to_object_path(
            self.implementation.apply_keyboard_with_task()
        )
