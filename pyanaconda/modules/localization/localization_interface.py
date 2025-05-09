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

from dasbus.server.interface import dbus_class, dbus_interface, dbus_signal
from dasbus.server.property import emits_properties_changed
from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.modules.common.base import KickstartModuleInterface
from pyanaconda.modules.common.constants.services import LOCALIZATION
from pyanaconda.modules.common.containers import TaskContainer
from pyanaconda.modules.common.structures.keyboard_layout import KeyboardLayout
from pyanaconda.modules.common.structures.language import LanguageData, LocaleData
from pyanaconda.modules.common.task import TaskInterface


@dbus_class
class KeyboardConfigurationTaskInterface(TaskInterface):
    """Interface to get keyboard configuration data."""

    @staticmethod
    def convert_result(value):
        """Convert value to publishable result.

        From:
        (("us", "cs (qwerty)"), "cs-qwerty")
        """
        return get_variant(Tuple[List[Str], Str], value)


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
        self.implementation.compositor_selected_layout_changed.connect(
            self.CompositorSelectedLayoutChanged
        )
        self.implementation.compositor_layouts_changed.connect(self.CompositorLayoutsChanged)

    def GetLanguages(self) -> List[Str]:
        """Get languages with available translations.

        For example: ["en", "cs"]

        :return: a list of language ids
        """
        return self.implementation.get_languages()

    def GetLanguageData(self, language_id: Str) -> Structure:
        """Get data about the specified language.

        :param: a language id (for example, "en")
        :return: a language data
        """
        language_data = self.implementation.get_language_data(language_id)
        return LanguageData.to_structure(language_data)

    def GetLocales(self, language_id: Str) -> List[Str]:
        """Get locales available for the specified language.

        For example: ["de_DE.UTF-8", "de_AT.UTF-8", ... ]

        :return: a list of locale ids
        """
        return self.implementation.get_locales(language_id)

    def GetCommonLocales(self) -> List[Str]:
        """Get a list of the most commonly used locales.

        For example: ["ar_EG.UTF-8", "en_US.UTF-8", "en_GB.UTF-8", ...]

        :return: a list of common locale IDs
        """
        return self.implementation.get_common_locales()

    def GetLocaleData(self, locale_id: Str) -> Structure:
        """Get data about the specified locale.

        :param: a locale id (for example, "en_US.UTF-8")
        :return: a locale data
        """
        locale_data = self.implementation.get_locale_data(locale_id)
        return LocaleData.to_structure(locale_data)

    def GetKeyboardLayouts(self) -> List[Structure]:
        """Get keyboard layouts.

        Returns a list of all available keyboard layouts.
        Each layout is represented as a `KeyboardLayout` structure.

        :return: List of `KeyboardLayout` structures
        """
        return KeyboardLayout.to_structure_list(
            self.implementation.get_keyboard_layouts()
        )

    @property
    def Language(self) -> Str:
        """The language the system will use."""
        return self.implementation.language

    @Language.setter
    @emits_properties_changed
    def Language(self, language: Str):
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

    @LanguageSupport.setter
    @emits_properties_changed
    def LanguageSupport(self, language_support: List[Str]):
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

    @LanguageKickstarted.setter
    @emits_properties_changed
    def LanguageKickstarted(self, language_seen: Bool):
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

    @VirtualConsoleKeymap.setter
    @emits_properties_changed
    def VirtualConsoleKeymap(self, vc_keymap: Str):
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

    @XLayouts.setter
    @emits_properties_changed
    def XLayouts(self, x_layouts: List[Str]):
        """Set the X layouts for the system.

        The layout is specified by values used by setxkbmap(1).  Accepts either
        layout format (eg "cz") or the layout(variant) format (eg "cz (qwerty)")

        :param x_layouts: List of x layout specifications.
        """
        self.implementation.set_x_layouts(x_layouts)

    @property
    def LayoutSwitchOptions(self) -> List[Str]:
        """List of options for layout switching"""
        return self.implementation.switch_options

    @LayoutSwitchOptions.setter
    @emits_properties_changed
    def LayoutSwitchOptions(self, switch_options: List[Str]):
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

    @KeyboardKickstarted.setter
    @emits_properties_changed
    def KeyboardKickstarted(self, keyboard_seen: Bool):
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

    def GetKeyboardConfigurationWithTask(self) -> ObjPath:
        """Get current keyboard configuration without storing it into module.

        This task will give you a potential configuration to be installed at the time of
        task execution. The task is read only, the results are not used anywhere by
        the localization module.
        """
        return TaskContainer.to_object_path(
            self.implementation.get_keyboard_configuration_with_task()
        )

    def ApplyKeyboardWithTask(self) -> ObjPath:
        """Apply keyboard configuration to the current system.

        :return: DBus path of the task applying the configuration
        """
        return TaskContainer.to_object_path(
            self.implementation.apply_keyboard_with_task()
        )

    def GetCompositorSelectedLayout(self) -> Str:
        """Get the activated keyboard layout.

        :return: Current keyboard layout (e.g. "cz (qwerty)")
        :rtype: str
        """
        return self.implementation.get_compositor_selected_layout()

    def SetCompositorSelectedLayout(self, layout_variant: Str) -> Bool:
        """Set the activated keyboard layout.

        :param layout_variant: The layout to set, with format "layout (variant)"
            (e.g. "cz (qwerty)")
        :type layout_variant: str
        :return: If the keyboard layout was activated
        :rtype: bool
        """
        return self.implementation.set_compositor_selected_layout(layout_variant)

    def SelectNextCompositorLayout(self):
        """Set the next available layout as active."""
        return self.implementation.select_next_compositor_layout()

    @dbus_signal
    def CompositorSelectedLayoutChanged(self, layout: Str):
        """Signal emitted when the selected keyboard layout changes."""
        pass

    def GetCompositorLayouts(self) -> List[Str]:
        """Get all available keyboard layouts.

        :return: A list of keyboard layouts (e.g. ["cz (qwerty)", cn (mon_todo_galik)])
        :rtype: list of strings
        """
        return self.implementation.get_compositor_layouts()

    def SetCompositorLayouts(self, layout_variants: List[Str], options: List[Str]):
        """Set the available keyboard layouts.

        :param layout_variants: A list of keyboard layouts (e.g. ["cz (qwerty)",
            cn (mon_todo_galik)])
        :type layout_variants: list of strings
        :param options: A list of switching options
        :type options: list of strings
        """
        self.implementation.set_compositor_layouts(layout_variants, options)

    @dbus_signal
    def CompositorLayoutsChanged(self, layouts: List[Str]):
        """Signal emitted when available layouts change."""
        pass
