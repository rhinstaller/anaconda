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
import os
import tempfile
import unittest
from contextlib import contextmanager
from textwrap import dedent
from unittest.mock import Mock, call, patch

import pytest

from pyanaconda.core.constants import DEFAULT_KEYBOARD, DEFAULT_VC_FONT
from pyanaconda.modules.common.errors.configuration import KeyboardConfigurationError
from pyanaconda.modules.common.errors.installation import KeyboardInstallationError
from pyanaconda.modules.localization.installation import (
    VC_CONF_FILE_PATH,
    X_CONF_DIR,
    X_CONF_FILE_NAME,
    KeyboardInstallationTask,
    LanguageInstallationTask,
    write_vc_configuration,
    write_x_configuration,
)
from pyanaconda.modules.localization.runtime import (
    ApplyKeyboardTask,
    AssignGenericKeyboardSettingTask,
    GetMissingKeyboardConfigurationTask,
    GetKeyboardConfigurationTask,
    try_to_load_keymap,
)
from pyanaconda.modules.localization.utils import get_missing_keyboard_configuration


class LanguageInstallationTaskTestCase(unittest.TestCase):
    """Test the language installation task."""

    def _run_task(self, lang, expected):
        """Run the installation task.

        :param lang: a value for LANG locale variable
        :param expected: a content of /etc/locale.conf
        """
        with tempfile.TemporaryDirectory() as root:
            # Prepare for the installation task.
            locale_conf = root + "/etc/locale.conf"
            os.makedirs(os.path.dirname(locale_conf), exist_ok=True)

            # Run the installation task.
            task = LanguageInstallationTask(root, lang)
            task.run()

            # Check the configuration file.
            with open(locale_conf) as f:
                content = f.read()

            assert content == expected

    @patch("pyanaconda.modules.localization.installation.execWithCapture")
    def test_invalid_locale(self, exec_mock):
        """Test an installation with an invalid locale."""
        exec_mock.return_value = "C.utf8"

        self._run_task("C.UTF-8", "LANG=\"C.UTF-8\"\n")
        self._run_task("en_US", "LANG=\"C.UTF-8\"\n")
        self._run_task("cs_CZ.UTF-8", "LANG=\"C.UTF-8\"\n")
        self._run_task("en_GB.ISO8859-15@euro", "LANG=\"C.UTF-8\"\n")

    @patch("pyanaconda.modules.localization.installation.execWithCapture")
    def test_unknown_locale(self, exec_mock):
        """Test an installation of a unknown locale."""
        exec_mock.side_effect = OSError("Fake!")

        self._run_task("C.UTF-8", "LANG=\"C.UTF-8\"\n")
        self._run_task("en_US", "LANG=\"en_US\"\n")
        self._run_task("cs_CZ.UTF-8", "LANG=\"cs_CZ.UTF-8\"\n")
        self._run_task("en_GB.ISO8859-15@euro", "LANG=\"en_GB.ISO8859-15@euro\"\n")

    @patch("pyanaconda.modules.localization.installation.execWithCapture")
    def test_valid_locale(self, exec_mock):
        """Test an installation of a valid locale."""
        locales = """
        C.utf8
        cs_CZ
        cs_CZ.iso88592
        cs_CZ.utf8
        en_US
        en_US.iso88591
        en_US.iso885915
        en_US.utf8
        """
        exec_mock.return_value = dedent(locales).strip()

        self._run_task("C.UTF-8", "LANG=\"C.UTF-8\"\n")
        self._run_task("en_US", "LANG=\"en_US\"\n")
        self._run_task("cs_CZ.UTF-8", "LANG=\"cs_CZ.UTF-8\"\n")
        self._run_task("en_GB.ISO8859-15@euro", "LANG=\"en_GB.ISO8859-15@euro\"\n")


class LocalizationTasksTestCase(unittest.TestCase):
    """Test tasks of the localization module."""

    @patch("pyanaconda.modules.localization.runtime.conf")
    def test_apply_keyboard_task_cant_activate(self, mocked_conf):
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
        assert result == (x_layouts, vc_keymap)

    @patch("pyanaconda.modules.localization.runtime.conf")
    def test_apply_keyboard_task_no_values(self, mocked_conf):
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
        assert result == (x_layouts, vc_keymap)

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
        assert result == (result_x_layouts, result_vc_keymap)

    def test_apply_keyboard_task(self):
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
    def test_get_missing_keyboard_configuration_task(self, get_missing_mock):
        """Test GetMissingKeyboardConfigurationTask."""
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
        assert result == (x_layouts_result, vc_keymap_result)

    @patch("pyanaconda.modules.localization.runtime.get_live_keyboard_instance")
    @patch("pyanaconda.modules.localization.runtime.get_missing_keyboard_configuration")
    def test_get_keyboard_configuration_task(self,
                                             get_missing_mock,
                                             get_live_keyboard_instance_mock):
        """Test GetKeyboardConfigurationTask."""
        x_layouts_result = "[cz (qwerty)]"
        vc_keymap_result = "cz-qwerty"
        get_missing_mock.return_value = (x_layouts_result, vc_keymap_result)
        mocked_localed = Mock()
        mocked_live_keyboard = Mock()
        get_live_keyboard_instance_mock.return_value = mocked_live_keyboard

        # test with unsupported layouts returns False
        mocked_live_keyboard.have_unsupported_layouts.return_value = False
        task = GetKeyboardConfigurationTask(
            localed_wrapper=mocked_localed,
            x_layouts="[cz (qwerty)]",
            vc_keymap="",
        )
        result = task.run()
        assert result == (x_layouts_result, vc_keymap_result, False)
        get_missing_mock.assert_called_once_with(mocked_localed,
                                                "[cz (qwerty)]",
                                                "",
                                                live_keyboard=mocked_live_keyboard)
        get_live_keyboard_instance_mock.assert_called_once_with()

        # test with unsupported layouts returns True
        get_live_keyboard_instance_mock.reset_mock()
        get_missing_mock.reset_mock()
        mocked_live_keyboard.have_unsupported_layouts.return_value = True
        task = GetKeyboardConfigurationTask(
            localed_wrapper=mocked_localed,
            x_layouts="",
            vc_keymap="",
        )
        result = task.run()
        assert result == (x_layouts_result, vc_keymap_result, True)
        get_missing_mock.assert_called_once_with(mocked_localed,
                                                "",
                                                "",
                                                live_keyboard=mocked_live_keyboard)
        get_live_keyboard_instance_mock.assert_called_once_with()

    @contextmanager
    def _create_localed_mock(self,
                             convert_layouts_output,
                             convert_keymap_output,
                             expected_convert_layouts_input=None,
                             expected_convert_keymap_input=None):
        localed = Mock()
        localed.convert_layouts.return_value = convert_layouts_output
        localed.convert_keymap.return_value = convert_keymap_output

        yield localed

        if expected_convert_layouts_input is None:
            localed.convert_layouts.assert_not_called()
        else:
            localed.convert_layouts.assert_called_once_with(expected_convert_layouts_input)

        if expected_convert_keymap_input is None:
            localed.convert_keymap.assert_not_called()
        else:
            localed.convert_keymap.assert_called_once_with(expected_convert_keymap_input)

    def _create_live_keyboard_mock(self, layouts):
        live_keyboard_mock = Mock()

        live_keyboard_mock.read_keyboard_layouts.return_value = layouts

        return live_keyboard_mock

    def _get_missing_keyboard_configuration_test(self,
                                                 input_x_layouts,
                                                 input_vc_keymap,
                                                 result_x_layouts,
                                                 result_vc_keymap,
                                                 localed,
                                                 live_keyboard):

        with patch("pyanaconda.modules.localization.utils.get_live_keyboard_instance") as \
             get_live_keyboard_mock:

            get_live_keyboard_mock.return_value = live_keyboard

            result = get_missing_keyboard_configuration(
                localed,
                input_x_layouts,
                input_vc_keymap
            )
            assert result == (result_x_layouts, result_vc_keymap)

    def test_get_missing_keyboard_configuration(self):
        """Test the get_missing_keyboard_configuration."""
        # No value available
        with self._create_localed_mock(
                convert_layouts_output="",
                convert_keymap_output=[DEFAULT_KEYBOARD],
                expected_convert_layouts_input=None,
                expected_convert_keymap_input=DEFAULT_KEYBOARD
        ) as mocked_localed:
            self._get_missing_keyboard_configuration_test(
                input_x_layouts=[],
                input_vc_keymap="",
                result_x_layouts=[DEFAULT_KEYBOARD],
                result_vc_keymap=DEFAULT_KEYBOARD,
                localed=mocked_localed,
                live_keyboard=None
            )
        # Both values available
        with self._create_localed_mock(
                convert_layouts_output="cz-qwerty",
                convert_keymap_output=["us"],
                expected_convert_layouts_input=None,
                expected_convert_keymap_input=None
        ) as mocked_localed:
            self._get_missing_keyboard_configuration_test(
                input_x_layouts=["cz (qwerty)"],
                input_vc_keymap="us",
                result_x_layouts=["cz (qwerty)"],
                result_vc_keymap="us",
                localed=mocked_localed,
                live_keyboard=None
            )
        # Only X laylouts available
        with self._create_localed_mock(
                convert_layouts_output="cz-qwerty",
                convert_keymap_output=["us"],
                expected_convert_layouts_input=["cz (qwerty)"],
                expected_convert_keymap_input=None
        ) as mocked_localed:
            self._get_missing_keyboard_configuration_test(
                input_x_layouts=["cz (qwerty)"],
                input_vc_keymap="",
                result_x_layouts=["cz (qwerty)"],
                result_vc_keymap="cz-qwerty",
                localed=mocked_localed,
                live_keyboard=None
            )
        # Only virtual console keymap available
        with self._create_localed_mock(
                convert_layouts_output="",
                convert_keymap_output=["us"],
                expected_convert_layouts_input=None,
                expected_convert_keymap_input="us"
        ) as mocked_localed:
            self._get_missing_keyboard_configuration_test(
                input_x_layouts=[],
                input_vc_keymap="us",
                result_x_layouts=["us"],
                result_vc_keymap="us",
                localed=mocked_localed,
                live_keyboard=None
            )

    def test_get_missing_keyboard_configuration_from_live(self):
        """Test the get_missing_keyboard_configuration from Live system."""
        # Take layouts from Live system but they are empty
        with self._create_localed_mock(
                convert_layouts_output="",
                convert_keymap_output=[DEFAULT_KEYBOARD],
                expected_convert_layouts_input=None,
                expected_convert_keymap_input=DEFAULT_KEYBOARD
        ) as mocked_localed:
            self._get_missing_keyboard_configuration_test(
                input_x_layouts=[],
                input_vc_keymap="",
                result_x_layouts=[DEFAULT_KEYBOARD],
                result_vc_keymap=DEFAULT_KEYBOARD,
                localed=mocked_localed,
                live_keyboard=self._create_live_keyboard_mock(layouts=[])
            )
        # Take layouts from Live system (vc_keymap is converted from live layouts)
        with self._create_localed_mock(
                convert_layouts_output="cz",
                convert_keymap_output=[],
                expected_convert_layouts_input=["cz", "us"],
                expected_convert_keymap_input=None
        ) as mocked_localed:
            self._get_missing_keyboard_configuration_test(
                input_x_layouts=[],
                input_vc_keymap="",
                result_x_layouts=["cz", "us"],
                result_vc_keymap="cz",
                localed=mocked_localed,
                live_keyboard=self._create_live_keyboard_mock(layouts=["cz", "us"])
            )
        # Layouts are set by user but vc_keymap not (convert layouts to VC without live)
        with self._create_localed_mock(
                convert_layouts_output="cz",
                convert_keymap_output=[],
                expected_convert_layouts_input=["cz"],
                expected_convert_keymap_input=None
        ) as mocked_localed:
            self._get_missing_keyboard_configuration_test(
                input_x_layouts=["cz"],
                input_vc_keymap="",
                result_x_layouts=["cz"],
                result_vc_keymap="cz",
                localed=mocked_localed,
                live_keyboard=self._create_live_keyboard_mock(layouts=[])
            )
        # VC keymap is set by user but layouts are taken from Live
        with self._create_localed_mock(
                convert_layouts_output="",
                convert_keymap_output=[],
                expected_convert_layouts_input=None,
                expected_convert_keymap_input=None
        ) as mocked_localed:
            self._get_missing_keyboard_configuration_test(
                input_x_layouts=[],
                input_vc_keymap="cz",
                result_x_layouts=["us"],
                result_vc_keymap="cz",
                localed=mocked_localed,
                live_keyboard=self._create_live_keyboard_mock(layouts=["us"])
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
        assert result == (result_x_layouts, result_vc_keymap)

    def test_assign_generic_keyboard_setting_task(self):

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
    def test_try_to_load_keymap(self, exec_with_redirect):
        """Test try_to_load_keymap function."""
        keymap = "us"

        exec_with_redirect.return_value = 0
        rc = try_to_load_keymap(keymap)
        exec_with_redirect.assert_called_once_with("loadkeys", [keymap])
        assert rc

        exec_with_redirect.reset_mock()
        exec_with_redirect.return_value = 1
        rc = try_to_load_keymap(keymap)
        exec_with_redirect.assert_called_once_with("loadkeys", [keymap])
        assert not rc

        exec_with_redirect.reset_mock()
        exec_with_redirect.side_effect = OSError("mock exception")
        with pytest.raises(KeyboardConfigurationError):
            rc = try_to_load_keymap(keymap)
        exec_with_redirect.assert_called_once_with("loadkeys", [keymap])

    def test_write_vc_configuration(self):
        """Test write_vc_configuration function."""
        with tempfile.TemporaryDirectory() as root:
            vc_keymap = "us"
            # /etc dir does not exist in root therefore the exception
            with pytest.raises(KeyboardInstallationError):
                write_vc_configuration(vc_keymap, root)

        with tempfile.TemporaryDirectory() as root:
            vc_keymap = "us"
            os.mkdir(os.path.join(root, "etc"))
            write_vc_configuration(vc_keymap, root)
            fpath = os.path.normpath(root + VC_CONF_FILE_PATH)
            # Check the result.
            with open(fpath) as f:
                assert f.read() == \
                    'KEYMAP="{}"\nFONT="{}"\n'.format(vc_keymap, DEFAULT_VC_FONT)

    @patch.dict(os.environ, {"LANG": "ru_RU.UTF-8"})
    def test_write_vc_configuration_env(self):
        """Test write_vc_configuration function for latarcyr console font."""
        with tempfile.TemporaryDirectory() as root:
            vc_keymap = "ru"
            vc_font = "latarcyrheb-sun16"
            os.mkdir(os.path.join(root, "etc"))
            write_vc_configuration(vc_keymap, root)
            fpath = os.path.normpath(root + VC_CONF_FILE_PATH)
            # Check the result.
            with open(fpath) as f:
                assert f.read() == \
                    'KEYMAP="{}"\nFONT="{}"\n'.format(vc_keymap, vc_font)

    def test_write_x_configuration(self):
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
    def test_keyboard_installation_task(self, write_vc_mock, write_x_mock, get_missing_mock):
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
