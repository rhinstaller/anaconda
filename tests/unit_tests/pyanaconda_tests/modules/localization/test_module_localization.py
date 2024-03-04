#
# Copyright (C) 2023  Red Hat, Inc.
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
# Red Hat Author(s): Radek Vykydal <rvykydal@redhat.com>
#
import unittest
import langtable

from unittest.mock import patch, Mock
from textwrap import dedent

from tests.unit_tests.pyanaconda_tests import check_kickstart_interface, \
    patch_dbus_publish_object, PropertiesChangedCallback, check_dbus_property, check_task_creation

from pyanaconda.modules.common.constants.services import LOCALIZATION
from pyanaconda.modules.common.structures.language import LanguageData, LocaleData
from pyanaconda.modules.localization.installation import LanguageInstallationTask, \
    KeyboardInstallationTask
from pyanaconda.modules.localization.localization import LocalizationService
from pyanaconda.modules.localization.localization_interface import LocalizationInterface
from pyanaconda.modules.localization.runtime import GetMissingKeyboardConfigurationTask, \
    ApplyKeyboardTask
from pyanaconda.modules.common.task import TaskInterface
from dasbus.typing import get_variant, Str, Bool
from dasbus.signal import Signal


class LocalizationInterfaceTestCase(unittest.TestCase):
    """Test DBus interface for the localization module."""

    def setUp(self):
        """Set up the localization module."""
        # Set up the localization module.
        self.localization_module = LocalizationService()
        self.localization_interface = LocalizationInterface(self.localization_module)

        # Connect to the properties changed signal.
        self.callback = PropertiesChangedCallback()
        self.localization_interface.PropertiesChanged.connect(self.callback)

    def _check_dbus_property(self, *args, **kwargs):
        check_dbus_property(
            LOCALIZATION,
            self.localization_interface,
            *args, **kwargs
        )

    def test_kickstart_properties(self):
        """Test kickstart properties."""
        assert self.localization_interface.KickstartCommands == ["keyboard", "lang"]
        assert self.localization_interface.KickstartSections == []
        assert self.localization_interface.KickstartAddons == []

    def test_language_property(self):
        """Test the Language property."""
        self._check_dbus_property(
            "Language",
            "cs_CZ.UTF-8"
        )

    def test_language_support_property(self):
        """Test the LanguageSupport property."""
        self._check_dbus_property(
            "LanguageSupport",
            ["fr_FR"]
        )

    def test_vc_keymap_property(self):
        """Test the VirtualConsoleKeymap property."""
        self._check_dbus_property(
            "VirtualConsoleKeymap",
            "cz"
        )

    def test_x_layouts_property(self):
        """Test the XLayouts property."""
        self._check_dbus_property(
            "XLayouts",
            ["cz(querty)"]
        )

    def test_switch_options_property(self):
        """Test the LayoutSwitchOptions property."""
        self._check_dbus_property(
            "LayoutSwitchOptions",
            ["grp:alt_shift_toggle"]
        )

    def test_keyboard_seen(self):
        """Test the KeyboardKickstarted property."""
        assert self.localization_interface.KeyboardKickstarted is False
        ks_in = """
        lang cs_CZ.UTF-8
        """
        ks_in = dedent(ks_in).strip()
        self.localization_interface.ReadKickstart(ks_in)
        assert self.localization_interface.KeyboardKickstarted is False
        ks_in = """
        lang cs_CZ.UTF-8
        keyboard cz
        """
        ks_in = dedent(ks_in).strip()
        self.localization_interface.ReadKickstart(ks_in)
        assert self.localization_interface.KeyboardKickstarted is True

    def test_language_seen(self):
        """Test the LanguageKickstarted property."""
        assert self.localization_interface.LanguageKickstarted is False
        ks_in = """
        keyboard cz
        """
        ks_in = dedent(ks_in).strip()
        self.localization_interface.ReadKickstart(ks_in)
        assert self.localization_interface.LanguageKickstarted is False
        ks_in = """
        keyboard cz
        lang cs_CZ.UTF-8
        """
        ks_in = dedent(ks_in).strip()
        self.localization_interface.ReadKickstart(ks_in)
        assert self.localization_interface.LanguageKickstarted is True

    def test_set_language_kickstarted(self):
        """Test LanguageKickstarted."""
        self._check_dbus_property(
            "LanguageKickstarted",
            True
        )

    def test_set_keyboard_kickstarted(self):
        """Test KeyboardKickstarted."""
        self._check_dbus_property(
            "KeyboardKickstarted",
            True
        )

    @patch("pyanaconda.modules.localization.runtime.try_to_load_keymap")
    def test_set_keyboard(self, mocked_load_keymap):
        """Test SetKeyboard."""
        # Makes sure VirtualConsoleKeymap setting will be used no matter the
        # conf.system.can_activate_keyboard value is.
        mocked_load_keymap.return_value = True
        self.localization_interface.SetKeyboard("us")
        assert self.localization_interface.VirtualConsoleKeymap == "us"

    def test_collect_requirements(self):
        """Test the CollectRequirements method."""
        # No default requirements.
        assert self.localization_interface.CollectRequirements() == []

    def test_languages(self):
        languages = list(self.localization_interface.GetLanguages())
        get_lang_data = self.localization_interface.GetLanguageData
        language_data = [
            LanguageData.from_structure(get_lang_data(language_id)) for language_id in languages
        ]

        assert len(languages) > 0
        assert language_data[0].english_name == "English"
        assert language_data[0].language_id == "en"
        assert language_data[0].is_common is True

    def test_language_data(self):
        get_lang_data = self.localization_interface.GetLanguageData
        data = get_lang_data('en')
        english = {
            "english-name": get_variant(Str, "English"),
            "is-common": get_variant(Bool, True),
            "language-id": get_variant(Str, 'en'),
            "native-name": get_variant(Str, "English"),
        }
        assert data == english

    def test_locales(self):
        locales = list(self.localization_interface.GetLocales("en"))
        get_locale_data = self.localization_interface.GetLocaleData
        locale_data = [
            LocaleData.from_structure(get_locale_data(locale_id)) for locale_id in locales
        ]

        assert len(locales) > 0
        assert locale_data[0].english_name == "English (United States)"
        assert locale_data[0].language_id == "en"
        assert locale_data[0].locale_id == "en_US.UTF-8"

    def test_locale_data(self):
        get_locale_data = self.localization_interface.GetLocaleData
        data = get_locale_data('en_US.UTF-8')

        english_us = {
            "english-name": get_variant(Str, "English (United States)"),
            "language-id": get_variant(Str, 'en'),
            "locale-id": get_variant(Str, 'en_US.UTF-8'),
            "native-name": get_variant(Str, "English (United States)"),
        }
        assert data == english_us

    def test_common_locales(self):
        common_locales = self.localization_interface.GetCommonLocales()

        assert isinstance(common_locales, list)
        assert "en_US.UTF-8" in common_locales
        assert "ja_JP.UTF-8" in common_locales
        assert self.localization_interface.GetCommonLocales() == langtable.list_common_locales()

    @patch_dbus_publish_object
    def test_install_with_task(self, publisher):
        """Test InstallWithTask."""
        self.localization_interface.Language = "cs_CZ.UTF-8"
        self.localization_interface.VirtualConsoleKeymap = 'us'
        self.localization_interface.XLayouts = ['cz', 'cz (qwerty)']
        self.localization_interface.LayoutSwitchOptions = ["grp:alt_shift_toggle"]

        tasks = self.localization_interface.InstallWithTasks()
        language_installation_task_path = tasks[0]
        keyboard_installation_task_path = tasks[1]

        publisher.assert_called()

        object_path = publisher.call_args_list[0][0][0]
        obj = publisher.call_args_list[0][0][1]

        assert language_installation_task_path == object_path
        assert isinstance(obj, TaskInterface)
        assert isinstance(obj.implementation, LanguageInstallationTask)
        assert obj.implementation._lang == "cs_CZ.UTF-8"

        object_path = publisher.call_args_list[1][0][0]
        obj = publisher.call_args_list[1][0][1]

        assert keyboard_installation_task_path == object_path
        assert isinstance(obj, TaskInterface)
        assert isinstance(obj.implementation, KeyboardInstallationTask)
        assert obj.implementation._x_layouts == ['cz', 'cz (qwerty)']
        assert obj.implementation._vc_keymap == 'us'
        assert obj.implementation._switch_options == ["grp:alt_shift_toggle"]

    @patch_dbus_publish_object
    def test_populate_missing_keyboard_configuration_with_task(self, publisher):
        """Test PopulateMissingKeyboardConfigurationWithTask."""
        self.localization_interface.VirtualConsoleKeymap = 'us'
        self.localization_interface.XLayouts = ['cz', 'cz (qwerty)']

        task_path = self.localization_interface.PopulateMissingKeyboardConfigurationWithTask()

        obj = check_task_creation(task_path, publisher, GetMissingKeyboardConfigurationTask)
        assert obj.implementation._vc_keymap == 'us'
        assert obj.implementation._x_layouts == ['cz', 'cz (qwerty)']

    @patch_dbus_publish_object
    def test_apply_keyboard_with_task(self, publisher):
        """Test ApplyKeyboardWithTask."""
        self.localization_interface.VirtualConsoleKeymap = 'us'
        self.localization_interface.XLayouts = ['cz', 'cz (qwerty)']
        self.localization_interface.LayoutSwitchOptions = ["grp:alt_shift_toggle"]

        task_path = self.localization_interface.ApplyKeyboardWithTask()

        obj = check_task_creation(task_path, publisher, ApplyKeyboardTask)
        assert obj.implementation._vc_keymap == 'us'
        assert obj.implementation._x_layouts == ['cz', 'cz (qwerty)']
        assert obj.implementation._switch_options == ["grp:alt_shift_toggle"]

    def _test_kickstart(self, ks_in, ks_out):
        check_kickstart_interface(self.localization_interface, ks_in, ks_out)

    def test_no_kickstart(self):
        """Test with no kickstart."""
        ks_in = None
        ks_out = ""
        self._test_kickstart(ks_in, ks_out)

    def test_kickstart_empty(self):
        """Test with empty string."""
        ks_in = ""
        ks_out = ""
        self._test_kickstart(ks_in, ks_out)

    def test_lang_kickstart(self):
        """Test the lang command."""
        ks_in = """
        lang cs_CZ.UTF-8
        """
        ks_out = """
        # System language
        lang cs_CZ.UTF-8
        """
        self._test_kickstart(ks_in, ks_out)

    def test_lang_kickstart2(self):
        """Test the lang command with added language support.."""
        ks_in = """
        lang en_US.UTF-8 --addsupport=cs_CZ.UTF-8
        """
        ks_out = """
        # System language
        lang en_US.UTF-8 --addsupport=cs_CZ.UTF-8
        """
        self._test_kickstart(ks_in, ks_out)

    def test_keyboard_kickstart1(self):
        """Test the keyboard command."""
        ks_in = """
        keyboard --vckeymap=us --xlayouts='us','cz (qwerty)'
        """
        ks_out = """
        # Keyboard layouts
        keyboard --vckeymap=us --xlayouts='us','cz (qwerty)'
        """
        self._test_kickstart(ks_in, ks_out)

    def test_keyboard_kickstart2(self):
        """Test the keyboard command."""
        ks_in = """
        keyboard us
        """
        ks_out = """
        # Keyboard layouts
        keyboard --vckeymap=us
        """
        self._test_kickstart(ks_in, ks_out)

    def test_keyboard_kickstart_ignore_generic_keyboard(self):
        """Test that keyboard argument is ignored if there is specific option."""
        ks_in = """
        keyboard --vckeymap cz us
        """
        ks_out = """
        # Keyboard layouts
        keyboard --vckeymap=cz
        """
        self._test_kickstart(ks_in, ks_out)

    @patch("pyanaconda.modules.localization.runtime.conf")
    @patch("pyanaconda.modules.localization.runtime.try_to_load_keymap")
    def test_keyboard_kickstart_keyboard_assign(self, mocked_load_keymap, mocked_conf):
        """Test the keyboard command assignment to proper setting (running a task with try_to_load_keymap)."""
        mocked_conf.system.can_activate_keyboard = True

        mocked_load_keymap.return_value = True
        ks_in = """
        keyboard us
        """
        ks_out = """
        # Keyboard layouts
        keyboard --vckeymap=us
        """
        self._test_kickstart(ks_in, ks_out)

        mocked_load_keymap.return_value = False
        ks_in = """
        keyboard us
        """
        ks_out = """
        # Keyboard layouts
        keyboard --xlayouts='us'
        """
        self._test_kickstart(ks_in, ks_out)

    def test_keyboard_kickstart3(self):
        """Test the keyboard command."""
        ks_in = """
        keyboard --xlayouts=cz,'cz (qwerty)' --switch=grp:alt_shift_toggle
        """
        ks_out = """
        # Keyboard layouts
        keyboard --xlayouts='cz','cz (qwerty)' --switch='grp:alt_shift_toggle'
        """
        self._test_kickstart(ks_in, ks_out)

    def test_keyboard_kickstart4(self):
        """Test the keyboard command."""
        ks_in = """
        keyboard --xlayouts='cz (qwerty)','en' en
        """
        ks_out = """
        # Keyboard layouts
        keyboard --xlayouts='cz (qwerty)','en'
        """
        self._test_kickstart(ks_in, ks_out)

    @patch("pyanaconda.modules.localization.localization.GkKeyboardManager")
    def test_compositor_layouts_api(self, gk_manager_cls):
        manager_class_mock = Mock()
        manager_class_mock.compositor_selected_layout_changed = Signal()
        manager_class_mock.compositor_layouts_changed = Signal()
        gk_manager_cls.return_value = manager_class_mock

        self.localization_module._compositor_keyboard_manager = None
        manager_mock = self.localization_module.compositor_keyboard_manager

        self.localization_interface.GetCompositorSelectedLayout()
        # pylint: disable=no-member
        manager_mock.get_compositor_selected_layout.assert_called_once()
        self.localization_interface.SetCompositorSelectedLayout("cz (qwerty)")
        # pylint: disable=no-member
        manager_mock.set_compositor_selected_layout.assert_called_once_with("cz (qwerty)")
        self.localization_interface.SelectNextCompositorLayout()
        # pylint: disable=no-member
        manager_mock.select_next_compositor_layout.assert_called_once()
        self.localization_interface.GetCompositorLayouts()
        # pylint: disable=no-member
        manager_mock.get_compositor_layouts.assert_called_once()
        self.localization_interface.SetCompositorLayouts(["cz (qwerty)", "cn (mon_todo_galik)"],
                                                         ["option"])
        # pylint: disable=no-member
        manager_mock.set_compositor_layouts.assert_called_once_with(
            ["cz (qwerty)", "cn (mon_todo_galik)"],
            ["option"]
        )

        # Test signals
        callback_mock = Mock()
        # pylint: disable=no-member
        self.localization_interface.CompositorSelectedLayoutChanged.connect(callback_mock)
        manager_class_mock.compositor_selected_layout_changed.emit("cz (qwerty)")
        callback_mock.assert_called_once_with("cz (qwerty)")

        callback_mock = Mock()
        # pylint: disable=no-member
        self.localization_interface.CompositorLayoutsChanged.connect(callback_mock)
        manager_class_mock.compositor_layouts_changed.emit(["cz (qwerty)", "cn (mon_todo_galik)"])
        callback_mock.assert_called_once_with(["cz (qwerty)", "cn (mon_todo_galik)"])

class LocalizationModuleTestCase(unittest.TestCase):
    """Test Localization module."""

    def setUp(self):
        """Set up the localization module."""
        # Set up the localization module.
        self.localization_module = LocalizationService()

    def test_set_from_generic_keyboard_setting(self):
        """Test set_from_generic_keyboard_setting_test ignores generic setting if it should."""
        self.localization_module.set_vc_keymap("cz")
        self.localization_module.set_x_layouts([])
        self.localization_module.set_from_generic_keyboard_setting("us")
        assert self.localization_module.vc_keymap == "cz"
        assert self.localization_module.x_layouts == []

        self.localization_module.set_vc_keymap("")
        self.localization_module.set_x_layouts(["cz"])
        self.localization_module.set_from_generic_keyboard_setting("us")
        assert self.localization_module.vc_keymap == ""
        assert self.localization_module.x_layouts == ["cz"]

    def test_update_settings_from_task(self):
        """Test _update_settings_from_task."""
        result = (["cz (qwerty)"], "us")
        self.localization_module._update_settings_from_task(result)
        assert self.localization_module.vc_keymap == "us"
        assert self.localization_module.x_layouts == ["cz (qwerty)"]
        result = ([], "")
        self.localization_module._update_settings_from_task(result)
        assert self.localization_module.vc_keymap == ""
        assert self.localization_module.x_layouts == []
