#
# Copyright (C) 2018  Red Hat, Inc.
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
import os
import tempfile
import unittest
from unittest.mock import patch, Mock, call

from textwrap import dedent

from tests.nosetests.pyanaconda_tests import check_kickstart_interface, patch_dbus_publish_object, \
        PropertiesChangedCallback, check_task_creation

from pyanaconda.core.constants import DEFAULT_KEYBOARD, DEFAULT_VC_FONT
from pyanaconda.modules.common.constants.services import LOCALIZATION
from pyanaconda.modules.common.errors.configuration import KeyboardConfigurationError
from pyanaconda.modules.common.errors.installation import KeyboardInstallationError
from pyanaconda.modules.localization.installation import LanguageInstallationTask, \
    KeyboardInstallationTask, write_vc_configuration, VC_CONF_FILE_PATH, write_x_configuration, \
    X_CONF_DIR, X_CONF_FILE_NAME
from pyanaconda.modules.localization.localization import LocalizationService
from pyanaconda.modules.localization.localed import get_missing_keyboard_configuration, \
    LocaledWrapper
from pyanaconda.modules.localization.localization_interface import LocalizationInterface
from pyanaconda.modules.localization.runtime import GetMissingKeyboardConfigurationTask, \
    ApplyKeyboardTask, AssignGenericKeyboardSettingTask, try_to_load_keymap
from pyanaconda.modules.common.task import TaskInterface


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

    def kickstart_properties_test(self):
        """Test kickstart properties."""
        self.assertEqual(self.localization_interface.KickstartCommands, ["keyboard", "lang"])
        self.assertEqual(self.localization_interface.KickstartSections, [])
        self.assertEqual(self.localization_interface.KickstartAddons, [])
        self.callback.assert_not_called()

    def language_property_test(self):
        """Test the Language property."""
        self.localization_interface.SetLanguage("cs_CZ.UTF-8")
        self.assertEqual(self.localization_interface.Language, "cs_CZ.UTF-8")
        self.callback.assert_called_once_with(LOCALIZATION.interface_name, {'Language': 'cs_CZ.UTF-8'}, [])

    def language_support_property_test(self):
        """Test the LanguageSupport property."""
        self.localization_interface.SetLanguageSupport(["fr_FR"])
        self.assertEqual(self.localization_interface.LanguageSupport, ["fr_FR"])
        self.callback.assert_called_once_with(LOCALIZATION.interface_name, {'LanguageSupport': ["fr_FR"]}, [])

    def vc_keymap_property_test(self):
        """Test the VirtualConsoleKeymap property."""
        self.localization_interface.SetVirtualConsoleKeymap("cz")
        self.assertEqual(self.localization_interface.VirtualConsoleKeymap, "cz")
        self.callback.assert_called_once_with(LOCALIZATION.interface_name, {'VirtualConsoleKeymap': 'cz'}, [])

    def x_layouts_property_test(self):
        """Test the XLayouts property."""
        self.localization_interface.SetXLayouts(["en", "cz(querty)"])
        self.assertEqual(self.localization_interface.XLayouts, ["en", "cz(querty)"])
        self.callback.assert_called_once_with(LOCALIZATION.interface_name, {'XLayouts': ["en", "cz(querty)"]}, [])

    def switch_options_property_test(self):
        """Test the LayoutSwitchOptions property."""
        self.localization_interface.SetLayoutSwitchOptions(["grp:alt_shift_toggle"])
        self.assertEqual(self.localization_interface.LayoutSwitchOptions, ["grp:alt_shift_toggle"])
        self.callback.assert_called_once_with(LOCALIZATION.interface_name, {'LayoutSwitchOptions': ["grp:alt_shift_toggle"]}, [])

    def keyboard_seen_test(self):
        """Test the KeyboardKickstarted property."""
        self.assertEqual(self.localization_interface.KeyboardKickstarted, False)
        ks_in = """
        lang cs_CZ.UTF-8
        """
        ks_in = dedent(ks_in).strip()
        self.localization_interface.ReadKickstart(ks_in)
        self.assertEqual(self.localization_interface.KeyboardKickstarted, False)
        ks_in = """
        lang cs_CZ.UTF-8
        keyboard cz
        """
        ks_in = dedent(ks_in).strip()
        self.localization_interface.ReadKickstart(ks_in)
        self.assertEqual(self.localization_interface.KeyboardKickstarted, True)

    def language_seen_test(self):
        """Test the LanguageKickstarted property."""
        self.assertEqual(self.localization_interface.LanguageKickstarted, False)
        ks_in = """
        keyboard cz
        """
        ks_in = dedent(ks_in).strip()
        self.localization_interface.ReadKickstart(ks_in)
        self.assertEqual(self.localization_interface.LanguageKickstarted, False)
        ks_in = """
        keyboard cz
        lang cs_CZ.UTF-8
        """
        ks_in = dedent(ks_in).strip()
        self.localization_interface.ReadKickstart(ks_in)
        self.assertEqual(self.localization_interface.LanguageKickstarted, True)

    def set_language_kickstarted_test(self):
        """Test SetLanguageKickstarted."""
        self.localization_interface.SetLanguageKickstarted(True)
        self.assertEqual(self.localization_interface.LanguageKickstarted, True)
        self.callback.assert_called_once_with(LOCALIZATION.interface_name, {'LanguageKickstarted': True}, [])

    def set_keyboard_kickstarted_test(self):
        """Test SetLanguageKickstarted."""
        self.localization_interface.SetKeyboardKickstarted(True)
        self.assertEqual(self.localization_interface.KeyboardKickstarted, True)
        self.callback.assert_called_once_with(LOCALIZATION.interface_name, {'KeyboardKickstarted': True}, [])

    @patch("pyanaconda.modules.localization.runtime.try_to_load_keymap")
    def set_keyboard_test(self, mocked_load_keymap):
        """Test SetKeyboard."""
        # Makes sure VirtualConsoleKeymap setting will be used no matter the
        # conf.system.can_activate_keyboard value is.
        mocked_load_keymap.return_value = True
        self.localization_interface.SetKeyboard("us")
        self.assertEqual(self.localization_interface.VirtualConsoleKeymap, "us")

    @patch_dbus_publish_object
    def install_with_task_test(self, publisher):
        """Test InstallWithTask."""
        self.localization_interface.SetLanguage("cs_CZ.UTF-8")
        self.localization_interface.SetVirtualConsoleKeymap('us')
        self.localization_interface.SetXLayouts(['cz', 'cz (qwerty)'])
        self.localization_interface.SetLayoutSwitchOptions(["grp:alt_shift_toggle"])

        tasks = self.localization_interface.InstallWithTasks()
        language_installation_task_path = tasks[0]
        keyboard_installation_task_path = tasks[1]

        publisher.assert_called()

        object_path = publisher.call_args_list[0][0][0]
        obj = publisher.call_args_list[0][0][1]

        self.assertEqual(language_installation_task_path, object_path)
        self.assertIsInstance(obj, TaskInterface)
        self.assertIsInstance(obj.implementation, LanguageInstallationTask)
        self.assertEqual(obj.implementation._lang, "cs_CZ.UTF-8")

        object_path = publisher.call_args_list[1][0][0]
        obj = publisher.call_args_list[1][0][1]

        self.assertEqual(keyboard_installation_task_path, object_path)
        self.assertIsInstance(obj, TaskInterface)
        self.assertIsInstance(obj.implementation, KeyboardInstallationTask)
        self.assertEqual(obj.implementation._x_layouts, ['cz', 'cz (qwerty)'])
        self.assertEqual(obj.implementation._vc_keymap, 'us')
        self.assertEqual(obj.implementation._switch_options, ["grp:alt_shift_toggle"])

    @patch_dbus_publish_object
    def populate_missing_keyboard_configuration_with_task_test(self, publisher):
        """Test PopulateMissingKeyboardConfigurationWithTask."""
        self.localization_interface.SetVirtualConsoleKeymap('us')
        self.localization_interface.SetXLayouts(['cz', 'cz (qwerty)'])

        task_path = self.localization_interface.PopulateMissingKeyboardConfigurationWithTask()

        obj = check_task_creation(self, task_path, publisher, GetMissingKeyboardConfigurationTask)
        self.assertEqual(obj.implementation._vc_keymap, 'us')
        self.assertEqual(obj.implementation._x_layouts, ['cz', 'cz (qwerty)'])

    @patch_dbus_publish_object
    def apply_keyboard_with_task_test(self, publisher):
        """Test ApplyKeyboardWithTask."""
        self.localization_interface.SetVirtualConsoleKeymap('us')
        self.localization_interface.SetXLayouts(['cz', 'cz (qwerty)'])
        self.localization_interface.SetLayoutSwitchOptions(["grp:alt_shift_toggle"])

        task_path = self.localization_interface.ApplyKeyboardWithTask()

        obj = check_task_creation(self, task_path, publisher, ApplyKeyboardTask)
        self.assertEqual(obj.implementation._vc_keymap, 'us')
        self.assertEqual(obj.implementation._x_layouts, ['cz', 'cz (qwerty)'])
        self.assertEqual(obj.implementation._switch_options, ["grp:alt_shift_toggle"])

    def _test_kickstart(self, ks_in, ks_out):
        check_kickstart_interface(self, self.localization_interface, ks_in, ks_out)

    def no_kickstart_test(self):
        """Test with no kickstart."""
        ks_in = None
        ks_out = ""
        self._test_kickstart(ks_in, ks_out)

    def kickstart_empty_test(self):
        """Test with empty string."""
        ks_in = ""
        ks_out = ""
        self._test_kickstart(ks_in, ks_out)

    def lang_kickstart_test(self):
        """Test the lang command."""
        ks_in = """
        lang cs_CZ.UTF-8
        """
        ks_out = """
        # System language
        lang cs_CZ.UTF-8
        """
        self._test_kickstart(ks_in, ks_out)

    def lang_kickstart2_test(self):
        """Test the lang command with added language support.."""
        ks_in = """
        lang en_US.UTF-8 --addsupport=cs_CZ.UTF-8
        """
        ks_out = """
        # System language
        lang en_US.UTF-8 --addsupport=cs_CZ.UTF-8
        """
        self._test_kickstart(ks_in, ks_out)

    def keyboard_kickstart1_test(self):
        """Test the keyboard command."""
        ks_in = """
        keyboard --vckeymap=us --xlayouts='us','cz (qwerty)'
        """
        ks_out = """
        # Keyboard layouts
        keyboard --vckeymap=us --xlayouts='us','cz (qwerty)'
        """
        self._test_kickstart(ks_in, ks_out)

    def keyboard_kickstart2_test(self):
        """Test the keyboard command."""
        ks_in = """
        keyboard us
        """
        ks_out = """
        # Keyboard layouts
        keyboard --vckeymap=us
        """
        self._test_kickstart(ks_in, ks_out)

    def keyboard_kickstart_ignore_generic_keyboard_test(self):
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
    def keyboard_kickstart_keyboard_assign_test(self, mocked_load_keymap, mocked_conf):
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

    def keyboard_kickstart3_test(self):
        """Test the keyboard command."""
        ks_in = """
        keyboard --xlayouts=cz,'cz (qwerty)' --switch=grp:alt_shift_toggle
        """
        ks_out = """
        # Keyboard layouts
        keyboard --xlayouts='cz','cz (qwerty)' --switch='grp:alt_shift_toggle'
        """
        self._test_kickstart(ks_in, ks_out)

    def keyboard_kickstart4_test(self):
        """Test the keyboard command."""
        ks_in = """
        keyboard --xlayouts='cz (qwerty)','en' en
        """
        ks_out = """
        # Keyboard layouts
        keyboard --xlayouts='cz (qwerty)','en'
        """
        self._test_kickstart(ks_in, ks_out)

class LocalizationModuleTestCase(unittest.TestCase):
    """Test Localization module."""

    def setUp(self):
        """Set up the localization module."""
        # Set up the localization module.
        self.localization_module = LocalizationService()

    def set_from_generic_keyboard_setting_test(self):
        """Test set_from_generic_keyboard_setting_test ignores generic setting if it should."""
        self.localization_module.set_vc_keymap("cz")
        self.localization_module.set_x_layouts([])
        self.localization_module.set_from_generic_keyboard_setting("us")
        self.assertEqual(self.localization_module.vc_keymap, "cz")
        self.assertEqual(self.localization_module.x_layouts, [])

        self.localization_module.set_vc_keymap("")
        self.localization_module.set_x_layouts(["cz"])
        self.localization_module.set_from_generic_keyboard_setting("us")
        self.assertEqual(self.localization_module.vc_keymap, "")
        self.assertEqual(self.localization_module.x_layouts, ["cz"])

    def update_settings_from_task_test(self):
        """Test _update_settings_from_task."""
        result = (["cz (qwerty)"], "us")
        self.localization_module._update_settings_from_task(result)
        self.assertEqual(self.localization_module.vc_keymap, "us")
        self.assertEqual(self.localization_module.x_layouts, ["cz (qwerty)"])
        result = ([], "")
        self.localization_module._update_settings_from_task(result)
        self.assertEqual(self.localization_module.vc_keymap, "")
        self.assertEqual(self.localization_module.x_layouts, [])


class LocalizationTasksTestCase(unittest.TestCase):
    """Test tasks of the localization module."""

    def language_installation_test(self):
        """Test the language installation task."""
        # Prepare sysroot.
        with tempfile.TemporaryDirectory() as root:

            # Prepare for the installation task.
            conf = root + "/etc/locale.conf"
            os.makedirs(os.path.dirname(conf), exist_ok=True)

            # Run the installation task.
            LanguageInstallationTask(root, "cs_CZ.UTF-8").run()

            # Check the result.
            with open(root + "/etc/locale.conf") as f:
                self.assertEqual(f.read(), "LANG=\"cs_CZ.UTF-8\"\n")

    @patch("pyanaconda.modules.localization.runtime.conf")
    def apply_keyboard_task_test_cant_acitvate(self, mocked_conf):
        """Test the ApplyKeyboardTest in can't activate keyboard environment."""
        mocked_conf.system.can_activate_keyboard = False
        x_layouts = ["cz (qwerty)"]
        vc_keymap = "us"
        task = ApplyKeyboardTask(
            localed_wrapper=Mock(),
            x_layouts=x_layouts,
            vc_keymap=vc_keymap,
            switch_options="grp:alt_shift_toggle"
        )
        result = task.run()
        self.assertEqual(result, (x_layouts, vc_keymap))

    @patch("pyanaconda.modules.localization.runtime.conf")
    def apply_keyboard_task_test_no_values(self, mocked_conf):
        """Test the ApplyKeyboardTest with no values to apply."""
        mocked_conf.system.can_activate_keyboard = True
        x_layouts = []
        vc_keymap = ""
        task = ApplyKeyboardTask(
            localed_wrapper=Mock(),
            x_layouts=x_layouts,
            vc_keymap=vc_keymap,
            switch_options="grp:alt_shift_toggle"
        )
        result = task.run()
        self.assertEqual(result, (x_layouts, vc_keymap))

    @patch("pyanaconda.modules.localization.runtime.write_vc_configuration")
    @patch("pyanaconda.modules.localization.runtime.conf")
    @patch("pyanaconda.modules.localization.runtime.try_to_load_keymap")
    def _apply_keyboard_task_test(self,
                                  mocked_load_keymap,
                                  mocked_conf,
                                  mocked_write_conf,
                                  x_layouts,
                                  converted_x_layouts,
                                  vc_keymap,
                                  converted_vc_keymap,
                                  load_keymap_result,
                                  result_x_layouts,
                                  result_vc_keymap):
        mocked_localed = Mock()
        mocked_conf.system.can_activate_keyboard = True
        mocked_load_keymap.return_value = load_keymap_result

        mocked_localed.set_and_convert_keymap.return_value = converted_vc_keymap
        mocked_localed.set_and_convert_layouts.return_value = converted_x_layouts

        switch_options = "grp:alt_shift_toggle"
        task = ApplyKeyboardTask(
            localed_wrapper=mocked_localed,
            x_layouts=x_layouts,
            vc_keymap=vc_keymap,
            switch_options=switch_options
        )
        result = task.run()
        self.assertEqual(result, (result_x_layouts, result_vc_keymap))

    def apply_keyboard_task_test(self):
        """Test the ApplyKeyboardTask."""

        load_keymap_result = True

        # pylint: disable=no-value-for-parameter
        self._apply_keyboard_task_test(
            x_layouts=["cz (qwerty)"],
            converted_x_layouts="cz-qwerty",
            vc_keymap="us",
            converted_vc_keymap=["us"],
            load_keymap_result=load_keymap_result,
            result_x_layouts=["cz (qwerty)"],
            result_vc_keymap="us",
        )
        self._apply_keyboard_task_test(
            x_layouts=[],
            converted_x_layouts="",
            vc_keymap="us",
            converted_vc_keymap=["us"],
            load_keymap_result=load_keymap_result,
            result_x_layouts=["us"],
            result_vc_keymap="us",
        )

        for load_keymap_result in (True, False):
            self._apply_keyboard_task_test(
                x_layouts=["cz (qwerty)"],
                converted_x_layouts="cz-qwerty",
                vc_keymap="",
                converted_vc_keymap=[""],
                load_keymap_result=load_keymap_result,
                result_x_layouts=["cz (qwerty)"],
                result_vc_keymap="cz-qwerty",
            )

        load_keymap_result = False

        self._apply_keyboard_task_test(
            x_layouts=["cz (qwerty)"],
            converted_x_layouts="cz-qwerty",
            vc_keymap="blah",
            converted_vc_keymap=[""],
            load_keymap_result=load_keymap_result,
            result_x_layouts=["cz (qwerty)"],
            result_vc_keymap="cz-qwerty",
        )
        self._apply_keyboard_task_test(
            x_layouts=[],
            converted_x_layouts="",
            vc_keymap="blah",
            converted_vc_keymap=[],
            load_keymap_result=load_keymap_result,
            result_x_layouts=[],
            result_vc_keymap="",
        )

    @patch("pyanaconda.modules.localization.runtime.get_missing_keyboard_configuration")
    def _get_missing_keyboard_configuration_task_test(self, get_missing_mock):
        x_layouts_result = "[cz (qwerty)]"
        vc_keymap_result = "cz-qwerty"
        get_missing_mock.return_value = (x_layouts_result, vc_keymap_result)
        mocked_localed = Mock()

        task = GetMissingKeyboardConfigurationTask(
            localed_wrapper=mocked_localed,
            x_layouts="[cz (qwerty)]",
            vc_keymap="",
        )
        result = task.run()
        self.assertEqual(result, (x_layouts_result, vc_keymap_result))

    def _get_missing_keyboard_configuration_test(self,
                                                 x_layouts,
                                                 converted_x_layouts,
                                                 vc_keymap,
                                                 converted_vc_keymap,
                                                 result_x_layouts,
                                                 result_vc_keymap):
        localed = Mock()
        localed.convert_keymap.return_value = converted_vc_keymap
        localed.convert_layouts.return_value = converted_x_layouts

        result = get_missing_keyboard_configuration(
            localed,
            x_layouts,
            vc_keymap
        )
        self.assertEqual(result, (result_x_layouts, result_vc_keymap))

    def get_missing_keyboard_configuration_test(self):
        """Test the get_missing_keyboard_configuration."""
        # No value available
        # pylint: disable=no-value-for-parameter
        self._get_missing_keyboard_configuration_test(
            x_layouts=[],
            converted_x_layouts="",
            vc_keymap="",
            converted_vc_keymap=[DEFAULT_KEYBOARD],
            result_x_layouts=[DEFAULT_KEYBOARD],
            result_vc_keymap=DEFAULT_KEYBOARD,
        )
        # Both values available
        self._get_missing_keyboard_configuration_test(
            x_layouts=["cz (qwerty)"],
            converted_x_layouts="cz-qwerty",
            vc_keymap="us",
            converted_vc_keymap=["us"],
            result_x_layouts=["cz (qwerty)"],
            result_vc_keymap="us",
        )
        # Only X laylouts available
        self._get_missing_keyboard_configuration_test(
            x_layouts=["cz (qwerty)"],
            converted_x_layouts="cz-qwerty",
            vc_keymap="",
            converted_vc_keymap=[""],
            result_x_layouts=["cz (qwerty)"],
            result_vc_keymap="cz-qwerty",
        )
        # Only virtual console keymap available
        self._get_missing_keyboard_configuration_test(
            x_layouts=[],
            converted_x_layouts="",
            vc_keymap="us",
            converted_vc_keymap=["us"],
            result_x_layouts=["us"],
            result_vc_keymap="us",
        )

    @patch("pyanaconda.modules.localization.runtime.conf")
    @patch("pyanaconda.modules.localization.runtime.try_to_load_keymap")
    def _assign_generic_keyboard_setting_task_test(self,
                                                   mocked_load_keymap,
                                                   mocked_conf,
                                                   can_activate_keyboard,
                                                   keyboard,
                                                   load_keymap_result,
                                                   result_x_layouts,
                                                   result_vc_keymap):
        mocked_conf.system.can_activate_keyboard = can_activate_keyboard
        mocked_load_keymap.return_value = load_keymap_result
        task = AssignGenericKeyboardSettingTask(
            keyboard=keyboard
        )
        result = task.run()
        self.assertEqual(result, (result_x_layouts, result_vc_keymap))

    def assign_generic_keyboard_setting_task_test(self):

        can_activate_keyboard = False

        # pylint: disable=no-value-for-parameter
        for load_keymap_result in (True, False):
            self._assign_generic_keyboard_setting_task_test(
                can_activate_keyboard=can_activate_keyboard,
                keyboard="cz",
                load_keymap_result=load_keymap_result,
                result_x_layouts=[],
                result_vc_keymap="cz"
            )
        for load_keymap_result in (True, False):
            self._assign_generic_keyboard_setting_task_test(
                can_activate_keyboard=can_activate_keyboard,
                keyboard="",
                load_keymap_result=load_keymap_result,
                result_x_layouts=[],
                result_vc_keymap=""
            )

        can_activate_keyboard = True

        for keyboard in ("cz", ""):
            self._assign_generic_keyboard_setting_task_test(
                can_activate_keyboard=can_activate_keyboard,
                keyboard=keyboard,
                load_keymap_result=True,
                result_x_layouts=[],
                result_vc_keymap=keyboard
            )
            self._assign_generic_keyboard_setting_task_test(
                can_activate_keyboard=can_activate_keyboard,
                keyboard=keyboard,
                load_keymap_result=False,
                result_x_layouts=[keyboard],
                result_vc_keymap=""
            )

    @patch("pyanaconda.modules.localization.runtime.execWithRedirect")
    def try_to_load_keymap_test(self, exec_with_redirect):
        """Test try_to_load_keymap function."""
        keymap = "us"

        exec_with_redirect.return_value = 0
        rc = try_to_load_keymap(keymap)
        exec_with_redirect.assert_called_once_with("loadkeys", [keymap])
        self.assertTrue(rc)

        exec_with_redirect.reset_mock()
        exec_with_redirect.return_value = 1
        rc = try_to_load_keymap(keymap)
        exec_with_redirect.assert_called_once_with("loadkeys", [keymap])
        self.assertFalse(rc)

        exec_with_redirect.reset_mock()
        exec_with_redirect.side_effect = OSError("mock exception")
        with self.assertRaises(KeyboardConfigurationError):
            rc = try_to_load_keymap(keymap)
        exec_with_redirect.assert_called_once_with("loadkeys", [keymap])

    def write_vc_configuration_test(self):
        """Test write_vc_configuration function."""
        with tempfile.TemporaryDirectory() as root:
            vc_keymap = "us"
            # /etc dir does not exist in root therefore the exception
            with self.assertRaises(KeyboardInstallationError):
                write_vc_configuration(vc_keymap, root)

        with tempfile.TemporaryDirectory() as root:
            vc_keymap = "us"
            os.mkdir(os.path.join(root, "etc"))
            write_vc_configuration(vc_keymap, root)
            fpath = os.path.normpath(root + VC_CONF_FILE_PATH)
            # Check the result.
            with open(fpath) as f:
                self.assertEqual(
                    f.read(),
                    'KEYMAP="{}"\nFONT="{}"\n'.format(vc_keymap, DEFAULT_VC_FONT)
                )

    def write_x_configuration_test(self):
        """Test write_x_configuration_test."""
        localed_wrapper = Mock()
        runtime_x_layouts = ["us (euro)"]
        runtime_options = []
        configured_x_layouts = ["cz (qwerty)"]
        configured_options = ["grp:alt_shift_toggle"]
        localed_wrapper.layouts_variants = runtime_x_layouts
        localed_wrapper.options = runtime_options

        def create_config(conf_dir):
            conf_file_path = os.path.join(conf_dir, X_CONF_FILE_NAME)
            if not os.path.exists(conf_file_path):
                os.mknod(conf_file_path)

        with tempfile.TemporaryDirectory() as mocked_root:
            root = os.path.join(mocked_root, "mnt/sysimage")
            os.makedirs(root)
            x_conf_dir_path = os.path.normpath(mocked_root + "/" + X_CONF_DIR)
            localed_wrapper.set_layouts.side_effect = lambda x, y: create_config(x_conf_dir_path)
            write_x_configuration(
                localed_wrapper,
                configured_x_layouts,
                configured_options,
                x_conf_dir_path,
                root
            )
            localed_wrapper.set_layouts.assert_has_calls([
                call(configured_x_layouts, configured_options),
                call(runtime_x_layouts, runtime_options),
            ])

    @patch("pyanaconda.modules.localization.installation.get_missing_keyboard_configuration")
    @patch("pyanaconda.modules.localization.installation.write_x_configuration")
    @patch("pyanaconda.modules.localization.installation.write_vc_configuration")
    def keyboard_installation_task_test(self, write_vc_mock, write_x_mock, get_missing_mock):
        localed = Mock()
        sysroot = "/mnt/sysimage"
        x_layouts = ["cz (qwerty)"]
        switch_options = ["grp:alt_shift_toggle"]
        vc_keymap = "us"

        task = KeyboardInstallationTask(
            localed_wrapper=localed,
            sysroot=sysroot,
            x_layouts=x_layouts,
            switch_options=switch_options,
            vc_keymap=vc_keymap
        )
        task.run()
        get_missing_mock.assert_not_called()
        write_x_mock.assert_called_once_with(
            localed,
            x_layouts,
            switch_options,
            X_CONF_DIR,
            sysroot
        )
        write_vc_mock.assert_called_once_with(
            vc_keymap,
            sysroot
        )

        x_layouts = ["cz (qwerty)"]
        vc_keymap = ""
        vc_keymap_from_conversion = "cz-qwerty"
        write_x_mock.reset_mock()
        write_vc_mock.reset_mock()
        get_missing_mock.reset_mock()
        get_missing_mock.return_value = (x_layouts, vc_keymap_from_conversion)
        task = KeyboardInstallationTask(
            localed_wrapper=localed,
            sysroot=sysroot,
            x_layouts=x_layouts,
            switch_options=switch_options,
            vc_keymap=vc_keymap
        )
        task.run()
        get_missing_mock.assert_called_once_with(
            localed,
            x_layouts,
            vc_keymap
        )
        write_x_mock.assert_called_once_with(
            localed,
            x_layouts,
            switch_options,
            X_CONF_DIR,
            sysroot
        )
        write_vc_mock.assert_called_once_with(
            vc_keymap_from_conversion,
            sysroot
        )

        x_layouts = []
        x_layouts_from_conversion = ["us"]
        vc_keymap = "us"
        write_x_mock.reset_mock()
        write_vc_mock.reset_mock()
        get_missing_mock.reset_mock()
        get_missing_mock.return_value = (x_layouts_from_conversion, vc_keymap)
        task = KeyboardInstallationTask(
            localed_wrapper=localed,
            sysroot=sysroot,
            x_layouts=x_layouts,
            switch_options=switch_options,
            vc_keymap=vc_keymap
        )
        task.run()
        get_missing_mock.assert_called_once_with(
            localed,
            x_layouts,
            vc_keymap
        )
        write_x_mock.assert_called_once_with(
            localed,
            x_layouts_from_conversion,
            switch_options,
            X_CONF_DIR,
            sysroot
        )
        write_vc_mock.assert_called_once_with(
            vc_keymap,
            sysroot
        )

        x_layouts = []
        vc_keymap = ""
        vc_keymap_default = DEFAULT_KEYBOARD
        x_layouts_from_conversion = [DEFAULT_KEYBOARD]
        write_x_mock.reset_mock()
        write_vc_mock.reset_mock()
        get_missing_mock.reset_mock()
        get_missing_mock.return_value = (x_layouts_from_conversion, vc_keymap_default)
        task = KeyboardInstallationTask(
            localed_wrapper=localed,
            sysroot=sysroot,
            x_layouts=x_layouts,
            switch_options=switch_options,
            vc_keymap=vc_keymap
        )
        task.run()
        get_missing_mock.assert_called_once_with(
            localed,
            x_layouts,
            vc_keymap
        )
        write_x_mock.assert_called_once_with(
            localed,
            x_layouts_from_conversion,
            switch_options,
            X_CONF_DIR,
            sysroot
        )
        write_vc_mock.assert_called_once_with(
            vc_keymap_default,
            sysroot
        )


class LocaledWrapperTestCase(unittest.TestCase):
    """Test LocaledWrapper."""

    @patch("pyanaconda.modules.localization.localed.conf")
    def localed_wrapper_no_systembus_conf_test(self, mocked_conf):
        """Test LocaledWrapper on environments with nonavailability of systembus configured."""
        mocked_conf.system.provides_system_bus = False
        localed_wrapper = LocaledWrapper()
        self._guarded_localed_wrapper_calls_check(localed_wrapper)

    def _guarded_localed_wrapper_calls_check(self, localed_wrapper):
        """Test that calls to LocaledWrapper are guarded not to fail."""
        self.assertEqual(localed_wrapper.keymap, "")
        self.assertEqual(localed_wrapper.options, [])
        self.assertEqual(localed_wrapper.layouts_variants, [])
        localed_wrapper.set_keymap("cz")
        localed_wrapper.set_keymap("cz", convert=True)
        localed_wrapper.convert_keymap("cz")
        localed_wrapper.set_and_convert_keymap("cz")
        localed_wrapper.set_layouts(["cz (qwerty)", "us (euro)"],
                                    options="grp:alt_shift_toggle",
                                    convert=True)
        localed_wrapper.set_and_convert_layouts(["cz (qwerty)", "us (euro)"])
        localed_wrapper.convert_layouts(["cz (qwerty)", "us (euro)"])
        localed_wrapper.set_layouts(["us-altgr-intl"])

    @patch("pyanaconda.modules.localization.localed.SystemBus")
    @patch("pyanaconda.modules.localization.localed.LOCALED")
    @patch("pyanaconda.modules.localization.localed.conf")
    def localed_wrapper_properties_test(self, mocked_conf, mocked_localed_service,
                                        mocked_system_bus):
        """Test conversion of return values from Localed service to LocaledWraper."""
        mocked_system_bus.check_connection.return_value = True
        mocked_conf.system.provides_system_bus = True
        mocked_localed_proxy = Mock()
        mocked_localed_service.get_proxy.return_value = mocked_localed_proxy
        localed_wrapper = LocaledWrapper()
        mocked_localed_proxy.VConsoleKeymap = "cz"
        mocked_localed_proxy.X11Layout = "cz,fi,us,fr"
        mocked_localed_proxy.X11Variant = "qwerty,,euro"
        mocked_localed_proxy.X11Options = "grp:alt_shift_toggle,grp:ctrl_alt_toggle"
        self.assertEqual(
            localed_wrapper.keymap,
            "cz"
        )
        self.assertEqual(
            localed_wrapper.layouts_variants,
            ["cz (qwerty)", "fi", "us (euro)", "fr"]
        )
        self.assertEqual(
            localed_wrapper.options,
            ["grp:alt_shift_toggle", "grp:ctrl_alt_toggle"]
        )

        mocked_localed_proxy.VConsoleKeymap = ""
        mocked_localed_proxy.X11Layout = ""
        mocked_localed_proxy.X11Variant = ""
        mocked_localed_proxy.X11Options = ""
        self.assertEqual(localed_wrapper.keymap, "")
        self.assertEqual(localed_wrapper.options, [])
        self.assertEqual(localed_wrapper.layouts_variants, [])

    @patch("pyanaconda.modules.localization.localed.SystemBus")
    @patch("pyanaconda.modules.localization.localed.LOCALED")
    @patch("pyanaconda.modules.localization.localed.conf")
    def localed_wrapper_safe_calls_test(self, mocked_conf, mocked_localed_service,
                                        mocked_system_bus):
        """Test calling LocaledWrapper with invalid values does not raise exception."""
        mocked_system_bus.check_connection.return_value = True
        mocked_conf.system.provides_system_bus = True
        mocked_localed_proxy = Mock()
        mocked_localed_service.get_proxy.return_value = mocked_localed_proxy
        mocked_localed_proxy.VConsoleKeymap = "cz"
        mocked_localed_proxy.X11Layout = "cz,fi,us,fr"
        mocked_localed_proxy.X11Variant = "qwerty,,euro"
        mocked_localed_proxy.X11Options = "grp:alt_shift_toggle,grp:ctrl_alt_toggle"
        localed_wrapper = LocaledWrapper()
        # valid values
        localed_wrapper.set_keymap("cz")
        localed_wrapper.set_keymap("cz", convert=True)
        localed_wrapper.convert_keymap("cz")
        localed_wrapper.set_and_convert_keymap("cz")
        # invalid values
        localed_wrapper.set_keymap("iinvalid")
        localed_wrapper.set_keymap("iinvalid", convert=True)
        localed_wrapper.convert_keymap("iinvalid")
        localed_wrapper.set_and_convert_keymap("iinvalid")
        # valid values
        localed_wrapper.set_layouts(["cz (qwerty)", "us (euro)"],
                                    options="grp:alt_shift_toggle",
                                    convert=True)
        localed_wrapper.set_and_convert_layouts(["cz (qwerty)", "us (euro)"])
        localed_wrapper.convert_layouts(["cz (qwerty)", "us (euro)"])
        # invalid values
        # rhbz#1843379
        localed_wrapper.set_layouts(["us-altgr-intl"])
        localed_wrapper.set_and_convert_layouts(["us-altgr-intl"])
        localed_wrapper.convert_layouts(["us-altgr-intl"])

    @patch("pyanaconda.modules.localization.localed.SystemBus")
    def localed_wrapper_no_systembus_test(self, mocked_system_bus):
        """Test LocaledWrapper in environment without system bus.

        Which is also the environment of our tests.
        """
        # Emulates mock environment
        mocked_system_bus.check_connection.return_value = False
        localed_wrapper = LocaledWrapper()
        self._guarded_localed_wrapper_calls_check(localed_wrapper)
