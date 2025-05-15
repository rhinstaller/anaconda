#
# Copyright (C) 2021  Red Hat, Inc.
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
# Test code from the startup_utils.py. Most of the parts are not
# easy to test but we can try to improve that.
#

import os
import unittest
from textwrap import dedent
from unittest.mock import Mock, PropertyMock, mock_open, patch

from pyanaconda.core.constants import (
    GEOLOC_CONNECTION_TIMEOUT,
    TIMEZONE_PRIORITY_GEOLOCATION,
    DisplayModes,
)
from pyanaconda.modules.common.structures.timezone import GeolocationData
from pyanaconda.startup_utils import (
    apply_geolocation_result,
    check_if_geolocation_should_be_used,
    print_dracut_errors,
    start_geolocation_conditionally,
    wait_for_geolocation_and_use,
)


class StartupUtilsTestCase(unittest.TestCase):

    def test_print_dracut_errors(self):
        logger_mock = Mock()

        with patch("pyanaconda.startup_utils.open", mock_open(read_data="test text")) as m:
            print_dracut_errors(logger_mock)

            m.assert_called_once_with("/run/anaconda/initrd_errors.txt", "rt")

            logger_mock.warning.assert_called_once_with(
                dedent("""
                ############## Installer errors encountered during boot ##############
                test text
                ############ Installer errors encountered during boot end ############"""))

    @patch("pyanaconda.core.constants.DRACUT_ERRORS_PATH", "None")
    def test_print_dracut_errors_missing_file(self):
        logger_mock = Mock()
        print_dracut_errors(logger_mock)
        logger_mock.assert_not_called()


class StartupUtilsGeolocTestCase(unittest.TestCase):
    """Test geolocation startup helpers."""

    @patch("pyanaconda.startup_utils.flags")
    @patch("pyanaconda.startup_utils.conf")
    def test_geoloc_check(self, conf_mock, flags_mock):
        """Test check_if_geolocation_should_be_used()

        This is a nasty function that actually takes 4 different "inputs". It is not possible to
        express these 16 combinations in a readable way, so pay attention to coverage - all code
        paths should be tested.
        """
        opts_mock = Mock()

        # dirinstall or image install
        flags_mock.automatedInstall = False
        conf_mock.target.is_hardware = False  # this causes False
        opts_mock.geoloc = None
        opts_mock.geoloc_use_with_ks = None
        assert check_if_geolocation_should_be_used(opts_mock, DisplayModes.GUI) is False

        # text mode
        flags_mock.automatedInstall = False
        conf_mock.target.is_hardware = True
        opts_mock.geoloc = None
        opts_mock.geoloc_use_with_ks = None
        assert check_if_geolocation_should_be_used(opts_mock, DisplayModes.TUI) is False

        # kickstart
        flags_mock.automatedInstall = True  # this causes False
        conf_mock.target.is_hardware = True
        opts_mock.geoloc = None
        opts_mock.geoloc_use_with_ks = None
        assert check_if_geolocation_should_be_used(opts_mock, DisplayModes.GUI) is False

        # kickstart + enable option
        flags_mock.automatedInstall = True  # this causes False
        conf_mock.target.is_hardware = True
        opts_mock.geoloc = None
        opts_mock.geoloc_use_with_ks = True  # this overrides it to True
        assert check_if_geolocation_should_be_used(opts_mock, DisplayModes.GUI) is True

        # disabled by option
        flags_mock.automatedInstall = False
        conf_mock.target.is_hardware = True
        opts_mock.geoloc = "0"  # this causes False
        opts_mock.geoloc_use_with_ks = None
        assert check_if_geolocation_should_be_used(opts_mock, DisplayModes.GUI) is False

        # enabled by option value
        flags_mock.automatedInstall = False
        conf_mock.target.is_hardware = True
        opts_mock.geoloc_use_with_ks = None
        for value in ("1", "yes", "whatever", "I typed here something"):  # anything causes True
            opts_mock.geoloc = value
            assert check_if_geolocation_should_be_used(opts_mock, DisplayModes.GUI) is True

        # normal install without boot options defaults to True
        flags_mock.automatedInstall = False
        conf_mock.target.is_hardware = True
        opts_mock.geoloc = None
        opts_mock.geoloc_use_with_ks = None
        assert check_if_geolocation_should_be_used(opts_mock, DisplayModes.GUI) is True

    @patch("pyanaconda.startup_utils.is_module_available")
    @patch("pyanaconda.startup_utils.check_if_geolocation_should_be_used")
    @patch("pyanaconda.startup_utils.TIMEZONE")
    def test_geoloc_start_no(self, tz_mock, check_mock, avail_mock):
        """Test geolocation is correctly skipped."""
        mock_opts = Mock()

        check_mock.return_value = False
        avail_mock.return_value = False
        assert start_geolocation_conditionally(mock_opts, DisplayModes.GUI) is None
        tz_mock.get_proxy.assert_not_called()

        check_mock.return_value = True
        avail_mock.return_value = False
        assert start_geolocation_conditionally(mock_opts, DisplayModes.GUI) is None
        tz_mock.get_proxy.assert_not_called()

        check_mock.return_value = False
        avail_mock.return_value = True
        assert start_geolocation_conditionally(mock_opts, DisplayModes.GUI) is None
        tz_mock.get_proxy.assert_not_called()

        check_mock.reset_mock()
        check_mock.return_value = False
        avail_mock.return_value = True
        assert start_geolocation_conditionally(mock_opts, DisplayModes.TUI) is None
        tz_mock.get_proxy.assert_not_called()
        check_mock.assert_called_once_with(mock_opts, DisplayModes.TUI)

    @patch("pyanaconda.startup_utils.is_module_available", return_value=True)
    @patch("pyanaconda.startup_utils.check_if_geolocation_should_be_used", return_value=True)
    @patch("pyanaconda.startup_utils.TIMEZONE")
    def test_geoloc_start_yes(self, tz_mock, check_mock, avail_mock):
        """Test geolocation is correctly skipped."""
        mock_opts = Mock()

        task_proxy = start_geolocation_conditionally(mock_opts, DisplayModes.GUI)
        tz_mock.get_proxy.assert_called()
        task_proxy.Start.assert_called_once_with()

    @patch("pyanaconda.startup_utils.apply_geolocation_result")
    @patch("pyanaconda.startup_utils.wait_for_task")
    def test_geoloc_wait(self, wait_mock, apply_mock):
        """Test waiting for geolocation."""
        mode_mock = Mock()

        # didn't start
        wait_for_geolocation_and_use(None, mode_mock)
        apply_mock.assert_not_called()
        wait_mock.assert_not_called()

        # all ok
        proxy_mock = Mock()
        wait_for_geolocation_and_use(proxy_mock, mode_mock)
        wait_mock.assert_called_once_with(proxy_mock, timeout=GEOLOC_CONNECTION_TIMEOUT)
        apply_mock.assert_called_once_with(mode_mock)
        wait_mock.reset_mock()
        apply_mock.reset_mock()

        # timeout
        proxy_mock = Mock()
        wait_mock.side_effect = TimeoutError
        with self.assertLogs(level="DEBUG") as cm:
            wait_for_geolocation_and_use(proxy_mock, mode_mock)
        wait_mock.assert_called_once_with(proxy_mock, timeout=GEOLOC_CONNECTION_TIMEOUT)
        apply_mock.assert_not_called()
        logs = "\n".join(cm.output)
        assert "timed out" in logs


def _setup_locale_wrapper(locale, module, text_mode=None):
    """Helper method to make mocks of setup_locale() return the right string."""
    return locale


class StartupUtilsGeolocApplyTestCase(unittest.TestCase):
    """Test applying geolocation results."""

    @patch.dict("os.environ", clear=True)
    @patch("pyanaconda.startup_utils.TIMEZONE")
    @patch("pyanaconda.startup_utils.LOCALIZATION")
    @patch("pyanaconda.startup_utils.GeolocationData")
    @patch("pyanaconda.startup_utils.setup_locale", side_effect=_setup_locale_wrapper)
    @patch("pyanaconda.startup_utils.locale_has_translation")
    def test_apply_none(self, has_trans_mock, setup_locale_mock, geodata_mock, loc_mock, tz_mock):
        """Test applying no geolocation results."""
        geodata_mock.from_structure.return_value = GeolocationData()
        tz_proxy = tz_mock.get_proxy.return_value
        tz_proxy.Timezone = PropertyMock()
        loc_proxy = loc_mock.get_proxy.return_value
        loc_proxy.Language = PropertyMock()

        apply_geolocation_result(None)

        tz_proxy.Timezone.assert_not_called()
        loc_proxy.Language.assert_not_called()
        setup_locale_mock.assert_not_called()
        assert not os.environ

    @patch.dict("os.environ", clear=True)
    @patch("pyanaconda.startup_utils.TIMEZONE")
    @patch("pyanaconda.startup_utils.LOCALIZATION")
    @patch("pyanaconda.startup_utils.GeolocationData")
    @patch("pyanaconda.startup_utils.setup_locale", side_effect=_setup_locale_wrapper)
    @patch("pyanaconda.startup_utils.locale_has_translation", return_value=True)
    def test_apply_all(self, has_trans_mock, setup_locale_mock, geodata_mock, loc_mock, tz_mock):
        """Test applying all geolocation results."""
        geodata_mock.from_structure.return_value = GeolocationData.from_values(
            territory="ES",
            timezone="Europe/Madrid"
        )
        tz_proxy = tz_mock.get_proxy.return_value
        loc_proxy = loc_mock.get_proxy.return_value
        loc_proxy.Language = ""

        apply_geolocation_result(None)

        tz_proxy.SetTimezoneWithPriority.assert_called_once_with(
            "Europe/Madrid",
            TIMEZONE_PRIORITY_GEOLOCATION
        )
        setup_locale_mock.assert_called_once_with("es_ES.UTF-8", loc_proxy, text_mode=False)
        assert os.environ == {"LANG": "es_ES.UTF-8"}

    @patch.dict("os.environ", clear=True)
    @patch("pyanaconda.startup_utils.TIMEZONE")
    @patch("pyanaconda.startup_utils.LOCALIZATION")
    @patch("pyanaconda.startup_utils.GeolocationData")
    @patch("pyanaconda.startup_utils.setup_locale", side_effect=_setup_locale_wrapper)
    @patch("pyanaconda.startup_utils.locale_has_translation", return_value=False)
    def test_apply_no_translation(self, has_trans_mock, setup_locale_mock, geodata_mock, loc_mock,
                                  tz_mock):
        """Test applying geolocation results with no translation."""
        geodata_mock.from_structure.return_value = GeolocationData.from_values(
            territory="ES",
            timezone="Europe/Madrid"
        )
        tz_proxy = tz_mock.get_proxy.return_value
        loc_proxy = loc_mock.get_proxy.return_value
        loc_proxy.Language = ""

        apply_geolocation_result(None)

        tz_proxy.SetTimezoneWithPriority.assert_called_once_with(
            "Europe/Madrid",
            TIMEZONE_PRIORITY_GEOLOCATION
        )
        setup_locale_mock.assert_not_called()
        assert not os.environ

    @patch.dict("os.environ", clear=True)
    @patch("pyanaconda.startup_utils.TIMEZONE")
    @patch("pyanaconda.startup_utils.LOCALIZATION")
    @patch("pyanaconda.startup_utils.GeolocationData")
    @patch("pyanaconda.startup_utils.setup_locale", side_effect=_setup_locale_wrapper)
    @patch("pyanaconda.startup_utils.locale_has_translation")
    def test_apply_lang_set(self, has_trans_mock, setup_locale_mock, geodata_mock, loc_mock,
                            tz_mock):
        """Test applying geolocation results when language has been set already."""
        geodata_mock.from_structure.return_value = GeolocationData.from_values(
            territory="ES",
            timezone="Europe/Madrid"
        )
        tz_proxy = tz_mock.get_proxy.return_value
        loc_proxy = loc_mock.get_proxy.return_value
        loc_proxy.Language = "ko_KO.UTF-8"
        loc_proxy.LanguageKickstarted = True

        apply_geolocation_result(None)

        tz_proxy.SetTimezoneWithPriority.assert_called_once_with(
            "Europe/Madrid",
            TIMEZONE_PRIORITY_GEOLOCATION
        )
        setup_locale_mock.assert_not_called()
        assert not os.environ

    @patch.dict("os.environ", clear=True)
    @patch("pyanaconda.startup_utils.TIMEZONE")
    @patch("pyanaconda.startup_utils.LOCALIZATION")
    @patch("pyanaconda.startup_utils.GeolocationData")
    @patch("pyanaconda.startup_utils.setup_locale", side_effect=_setup_locale_wrapper)
    @patch("pyanaconda.startup_utils.locale_has_translation", return_value=True)
    def test_apply_tz_missing(self, has_trans_mock, setup_locale_mock, geodata_mock, loc_mock,
                              tz_mock):
        """Test applying language from geolocation when timezone is missing."""
        geodata_mock.from_structure.return_value = GeolocationData.from_values(
            territory="ES",
            timezone=""
        )
        tz_proxy = tz_mock.get_proxy.return_value
        tz_proxy.Timezone = ""
        loc_proxy = loc_mock.get_proxy.return_value
        loc_proxy.Language = ""

        apply_geolocation_result(None)

        tz_proxy.SetTimezone.assert_not_called()
        tz_proxy.SetTimezoneWithPriority.assert_not_called()
        setup_locale_mock.assert_called_once_with("es_ES.UTF-8", loc_proxy, text_mode=False)
        assert os.environ == {"LANG": "es_ES.UTF-8"}
