#
# Kickstart module for language and keyboard settings.
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
import langtable

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.dbus import DBus
from pyanaconda.core.signal import Signal
from pyanaconda.localization import (
    _build_layout_infos,
    _get_layout_variant_description,
    get_available_translations,
    get_common_keyboard_layouts,
    get_common_languages,
    get_english_name,
    get_language_id,
    get_language_locales,
    get_native_name,
    layout_supports_ascii,
)
from pyanaconda.modules.common.base import KickstartService
from pyanaconda.modules.common.constants.services import LOCALIZATION
from pyanaconda.modules.common.containers import TaskContainer
from pyanaconda.modules.common.structures.keyboard_layout import KeyboardLayout
from pyanaconda.modules.common.structures.language import LanguageData, LocaleData
from pyanaconda.modules.localization.installation import (
    KeyboardInstallationTask,
    LanguageInstallationTask,
)
from pyanaconda.modules.localization.kickstart import LocalizationKickstartSpecification
from pyanaconda.modules.localization.localed import (
    CompositorLocaledWrapper,
    LocaledWrapper,
)
from pyanaconda.modules.localization.localization_interface import LocalizationInterface
from pyanaconda.modules.localization.runtime import (
    ApplyKeyboardTask,
    AssignGenericKeyboardSettingTask,
    GetMissingKeyboardConfigurationTask,
)

log = get_module_logger(__name__)

class LocalizationService(KickstartService):
    """The Localization service."""

    def __init__(self):
        super().__init__()
        self.language_changed = Signal()
        self._language = ""

        self.language_support_changed = Signal()
        self._language_support = []

        self.language_seen_changed = Signal()
        self._language_seen = False

        self.vc_keymap_changed = Signal()
        self._vc_keymap = ""

        self.x_layouts_changed = Signal()
        self._x_layouts = []

        self.switch_options_changed = Signal()
        self._switch_options = []

        self.keyboard_seen_changed = Signal()
        self._keyboard_seen = False

        self.compositor_selected_layout_changed = Signal()
        self.compositor_layouts_changed = Signal()

        self._layout_infos = _build_layout_infos()

        self._localed_wrapper = None
        self._localed_compositor_wrapper = None

    def publish(self):
        """Publish the module."""
        TaskContainer.set_namespace(LOCALIZATION.namespace)
        DBus.publish_object(LOCALIZATION.object_path, LocalizationInterface(self))
        DBus.register_service(LOCALIZATION.service_name)

    @property
    def kickstart_specification(self):
        """Return the kickstart specification."""
        return LocalizationKickstartSpecification

    def process_kickstart(self, data):
        """Process the kickstart data."""
        # lang
        self.set_language(data.lang.lang)
        self.set_language_support(data.lang.addsupport)

        self.set_language_seen(data.lang.seen)

        # keyboard
        self.set_vc_keymap(data.keyboard.vc_keymap)
        self.set_x_layouts(data.keyboard.x_layouts)
        self.set_switch_options(data.keyboard.switch_options)

        if data.keyboard._keyboard:
            self.set_from_generic_keyboard_setting(data.keyboard._keyboard)

        self.set_keyboard_seen(data.keyboard.seen)

    def setup_kickstart(self, data):
        """Set up the kickstart data."""
        # lang
        data.lang.lang = self.language
        data.lang.addsupport = self.language_support

        # keyboard
        data.keyboard.vc_keymap = self.vc_keymap
        data.keyboard.x_layouts = self.x_layouts
        data.keyboard.switch_options = self.switch_options

    def get_languages(self):
        """Get languages with available translations.

        For example: ["en", "cs"]

        :return: a list of language ids
        """
        return get_available_translations()

    def get_language_data(self, language_id):
        """Get data about the specified language.

        :param: a language id (for example, "en")
        :return: a language data
        """
        tdata = LanguageData()
        tdata.english_name = get_english_name(language_id)
        tdata.is_common = language_id in get_common_languages()
        tdata.language_id = language_id
        tdata.native_name = get_native_name(language_id)

        return tdata

    def get_locales(self, language_id):
        """Get locales available for the specified language.

        For example: ["de_DE.UTF-8", "de_AT.UTF-8", ... ]

        :return: a list of locale ids
        """
        return get_language_locales(language_id)

    def get_common_locales(self):
        """Get a list of the most commonly used locales.

        For example: ["ar_EG.UTF-8", "en_US.UTF-8", "en_GB.UTF-8", ...]

        :return: a list of common locale IDs
        """
        return langtable.list_common_locales()

    def get_locale_data(self, locale_id):
        """Get data about the specified locale.

        :param: a locale id (for example, "en_US.UTF-8")
        :return: a locale data
        """
        tdata = LocaleData()
        tdata.english_name = get_english_name(locale_id)
        tdata.language_id = get_language_id(locale_id)
        tdata.locale_id = locale_id
        tdata.native_name = get_native_name(locale_id)

        return tdata

    def get_layout_variant_description(self, layout_variant, with_lang=True, xlated=True):
        """
        Return a description of the given layout-variant.

        :param layout_variant: Layout-variant identifier (e.g., 'cz (qwerty)')
        :param with_lang: Include the language in the description if available
        :param xlated: Return a translated version of the description if True
        :return: Formatted layout description
        """

        return _get_layout_variant_description(layout_variant, self._layout_infos, with_lang, xlated)

    def get_keyboard_layouts(self):
        """Get localized keyboard layouts

        :return: list of dictionaries with keyboard layout information
        """
        # rxkb_context.layouts lists all XKB layouts, including variants and less common options,
        # while langtable.list_keyboards filters for the most relevant layouts.
        keyboards = self._layout_infos.items()
        common_langtable_keyboards = get_common_keyboard_layouts()
        common_languages = [self.get_language_data(lang).english_name for lang in get_common_languages()]

        layouts = []
        for name, info in keyboards:
            if name:
                is_common_lang = any(entry.split('; ')[0] in common_languages for entry in info.langs)
                layout = KeyboardLayout()
                layout.layout_id = name
                layout.description = self.get_layout_variant_description(name, with_lang=True, xlated=True)
                layout.is_common = name.replace(" ", "") in common_langtable_keyboards and is_common_lang
                layout.langs = info.langs
                layout.supports_ascii = layout_supports_ascii(name.replace(" ", ""))
                layouts.append(layout)

        return layouts

    @property
    def language(self):
        """Return the language."""
        return self._language

    def set_language(self, language):
        """Set the language."""
        self._language = language
        self.language_changed.emit()
        log.debug("Language is set to %s.", language)

    @property
    def language_support(self):
        """Return suppored languages."""
        return self._language_support

    def set_language_support(self, language_support):
        """Set supported languages."""
        self._language_support = language_support
        self.language_support_changed.emit()
        log.debug("Language support is set to %s.", language_support)

    @property
    def language_seen(self):
        """Was language command seen in kickstart?"""
        return self._language_seen

    def set_language_seen(self, seen):
        """Set whether language command was seen in kickstart."""
        self._language_seen = seen
        self.language_seen_changed.emit()
        log.debug("Language seen set to %s.", seen)

    @property
    def vc_keymap(self):
        """Return virtual console keymap."""
        return self._vc_keymap

    def set_vc_keymap(self, vc_keymap):
        """Set virtual console keymap."""
        self._vc_keymap = vc_keymap
        self.vc_keymap_changed.emit()
        log.debug("Virtual console keymap is set to %s.", vc_keymap)

    @property
    def x_layouts(self):
        """Return X Keyboard Layouts."""
        return self._x_layouts

    def set_x_layouts(self, x_layouts):
        """Set X Keyboard Layouts."""
        self._x_layouts = x_layouts
        self.x_layouts_changed.emit()
        log.debug("X Layouts are set to %s.", x_layouts)

    @property
    def switch_options(self):
        """Return X layout switching options."""
        return self._switch_options

    def set_switch_options(self, switch_options):
        """Set X layout switching options."""
        self._switch_options = switch_options
        self.switch_options_changed.emit()
        log.debug("X layout switch options are set to %s.", switch_options)

    @property
    def keyboard_seen(self):
        """Was keyboard command seen in kickstart?"""
        return self._keyboard_seen

    def set_keyboard_seen(self, keyboard_seen):
        """Set whether keyboard command was seen in kickstart."""
        self._keyboard_seen = keyboard_seen
        self.keyboard_seen_changed.emit()
        log.debug("keyboard command considered seen in kicksatart: %s.", keyboard_seen)

    @property
    def localed_wrapper(self):
        if not self._localed_wrapper:
            self._localed_wrapper = LocaledWrapper()

        return self._localed_wrapper

    @property
    def localed_compositor_wrapper(self):
        if not self._localed_compositor_wrapper:
            self._localed_compositor_wrapper = CompositorLocaledWrapper()

            self._localed_compositor_wrapper.compositor_selected_layout_changed.connect(
                self.compositor_selected_layout_changed.emit
            )
            self._localed_compositor_wrapper.compositor_layouts_changed.connect(
                self.compositor_layouts_changed.emit
            )
        return self._localed_compositor_wrapper

    def install_with_tasks(self):
        """Return the installation tasks of this module.

        :returns: list of installation tasks
        """
        return [
            LanguageInstallationTask(
                sysroot=conf.target.system_root,
                lang=self.language
            ),
            KeyboardInstallationTask(
                sysroot=conf.target.system_root,
                localed_wrapper=self.localed_wrapper,
                x_layouts=self.x_layouts,
                switch_options=self.switch_options,
                vc_keymap=self.vc_keymap
            )
        ]

    def populate_missing_keyboard_configuration_with_task(self):
        """Populate missing keyboard configuration.

        The configuration is populated by conversion and/or default values.

        :returns: a task getting missing keyboard configuration
        """
        task = GetMissingKeyboardConfigurationTask(
            localed_wrapper=self.localed_wrapper,
            x_layouts=self.x_layouts,
            vc_keymap=self.vc_keymap,
        )
        task.succeeded_signal.connect(lambda: self._update_settings_from_task(task.get_result()))
        return task

    def _update_settings_from_task(self, result):
        """Update settings from task result."""
        x_layouts, vc_keymap = result
        self.set_vc_keymap(vc_keymap)
        self.set_x_layouts(x_layouts)

    def get_keyboard_configuration_with_task(self):
        """Get current keyboard configuration without storing it into module.

        This configuration will be used for the installation at the time of task execution.
        The task is read only, the results are not stored anywhere.

        :returns: a task reading keyboard configuration
        """
        task = GetMissingKeyboardConfigurationTask(
            localed_wrapper=self.localed_wrapper,
            x_layouts=self.x_layouts,
            vc_keymap=self.vc_keymap,
        )
        return task

    def apply_keyboard_with_task(self):
        """Apply keyboard configuration to the current system.

        :returns: a task applying the configuration
        """
        task = ApplyKeyboardTask(
            localed_wrapper=self.localed_wrapper,
            x_layouts=self.x_layouts,
            vc_keymap=self.vc_keymap,
            switch_options=self.switch_options
        )
        task.succeeded_signal.connect(lambda: self._update_settings_from_task(task.get_result()))
        return task

    def set_from_generic_keyboard_setting(self, keyboard):
        """Set keyboard from generic keyboard setting

        :param keyboard:
        """
        log.debug("Setting keyboard from generic setting value '%s'.", keyboard)
        if self.vc_keymap or self.x_layouts:
            log.debug("Ignoring generic keyboard setting as we have a specific one.")
            return

        task = AssignGenericKeyboardSettingTask(
            keyboard=keyboard
        )
        result = task.run()
        self._update_settings_from_task(result)

    def get_compositor_selected_layout(self):
        return self.localed_compositor_wrapper.current_layout_variant

    def set_compositor_selected_layout(self, layout_variant):
        return self.localed_compositor_wrapper.select_layout(layout_variant)

    def select_next_compositor_layout(self):
        return self.localed_compositor_wrapper.select_next_layout()

    def get_compositor_layouts(self):
        return self.localed_compositor_wrapper.get_layouts_variants()

    def set_compositor_layouts(self, layout_variants, options):
        self.localed_compositor_wrapper.set_layouts(layout_variants, options)
