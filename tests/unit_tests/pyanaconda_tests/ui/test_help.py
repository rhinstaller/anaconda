#
# Copyright (C) 2020  Red Hat, Inc.
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
import os
import tempfile

import unittest
from unittest.mock import patch

from pyanaconda.core.constants import DisplayModes
from pyanaconda.ui.lib.help import _get_help_mapping, show_graphical_help, _get_help_args, \
    HelpArguments, get_help_path_for_screen, show_graphical_help_for_screen, localize_help_file, \
    _get_help_args_for_screen

INVALID_MAPPING = """
This is an invalid mapping.
"""

GUI_MAPPING = """
{
  "_default_": {
    "file": "Installation_Guide.xml",
    "anchor": ""
  },
  "installation-summary": {
    "file": "SummaryHub.xml",
    "anchor": ""
  },
    "user-configuration": {
    "file": "UserSpoke.xml",
    "anchor": "create-user"
  }
}
"""

TUI_MAPPING = """
{
  "_default_": {
    "file": "Installation_Guide.txt"
  },
  "installation-summary": {
    "file": "SummaryHub.txt"
  },
  "user-configuration": {
    "file": "UserSpoke.txt"
  }
}
"""


class HelpSupportTestCase(unittest.TestCase):
    """Test the built-in help support."""

    def tearDown(self):
        """Clean up after a test."""
        _get_help_mapping.cache_clear()

    def _create_file(self, file_dir, file_name, file_content):
        """Create a file with the help mapping."""
        os.makedirs(file_dir, exist_ok=True)
        file_path = os.path.join(file_dir, file_name)

        with open(file_path, mode="w") as f:
            f.write(file_content)

    @patch('pyanaconda.ui.lib.help.conf')
    def test_get_help_mapping(self, conf_mock):
        """Test the _get_help_mapping function."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            conf_mock.ui.help_directory = tmp_dir

            _get_help_mapping.cache_clear()
            assert _get_help_mapping(DisplayModes.TUI) == {}

            _get_help_mapping.cache_clear()
            self._create_file(tmp_dir, "anaconda-tui.json", INVALID_MAPPING)
            assert _get_help_mapping(DisplayModes.TUI) == {}

            _get_help_mapping.cache_clear()
            self._create_file(tmp_dir, "anaconda-gui.json", GUI_MAPPING)
            assert _get_help_mapping(DisplayModes.GUI) == {
                "_default_": {
                    "file": "Installation_Guide.xml",
                    "anchor": ""
                },
                "installation-summary": {
                    "file": "SummaryHub.xml",
                    "anchor": ""
                },
                "user-configuration": {
                    "file": "UserSpoke.xml",
                    "anchor": "create-user"
                }
            }

    @patch('pyanaconda.ui.lib.help.conf')
    def test_get_help_args(self, conf_mock):
        """Test the _get_help_args function."""
        conf_mock.ui.help_directory = "/fake/path"

        mapping = {
            "_default_": {
                "file": "Installation_Guide.xml",
                "anchor": ""
            },
            "installation-summary": {
                "file": "SummaryHub.xml",
                "anchor": ""
            },
            "user-configuration": {
                "file": "UserSpoke.xml",
                "anchor": "create-user"
            }
        }

        assert _get_help_args({}, "") == \
            HelpArguments("", "", "")

        assert _get_help_args({}, "installation-summary") == \
            HelpArguments("", "", "")

        assert _get_help_args(mapping, "installation-summary") == \
            HelpArguments("", "SummaryHub.xml", "")

        assert _get_help_args(mapping, "user-configuration") == \
            HelpArguments("", "UserSpoke.xml", "create-user")

        assert _get_help_args(mapping, "unknown-spoke") == \
            HelpArguments("", "", "")

    def test_localize_help_file(self):
        """Test the localize_help_file function."""
        with tempfile.TemporaryDirectory() as tmp_dir:

            # No available file.
            assert localize_help_file("file.txt", tmp_dir, "cs_CZ.UTF-8") is None

            # File in default locale.
            self._create_file(
                file_name="file.txt",
                file_dir=os.path.join(tmp_dir, "en-US"),
                file_content="<content for en_US.UTF-8>"
            )

            assert localize_help_file("file.txt", tmp_dir, "cs_CZ.UTF-8") == \
                os.path.join(tmp_dir, "en-US", "file.txt")

            # File in both locales.
            self._create_file(
                file_name="file.txt",
                file_dir=os.path.join(tmp_dir, "cs-CZ"),
                file_content="<content for cs_CZ.UTF-8>"
            )

            assert localize_help_file("file.txt", tmp_dir, "cs_CZ.UTF-8") == \
                os.path.join(tmp_dir, "cs-CZ", "file.txt")

    @patch('pyanaconda.ui.lib.help.conf')
    def test_get_help_args_for_screen(self, conf_mock):
        """Test the _get_help_args_for_screen function."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            conf_mock.ui.help_directory = tmp_dir
            content_dir = os.path.join(tmp_dir, "en-US")

            # No mapping.
            _get_help_mapping.cache_clear()
            assert _get_help_args_for_screen(DisplayModes.GUI, "installation-summary") is None

            # No help and no default.
            _get_help_mapping.cache_clear()
            self._create_file(tmp_dir, "anaconda-gui.json", GUI_MAPPING)
            assert _get_help_args_for_screen(DisplayModes.GUI, "installation-summary") is None

            # No help, return default.
            self._create_file(content_dir, "Installation_Guide.xml", "<guide>")
            help_path = os.path.join(tmp_dir, "en-US", "Installation_Guide.xml")

            assert _get_help_args_for_screen(DisplayModes.GUI, "installation-summary") == \
                HelpArguments(help_path, "Installation_Guide.xml", "")

            # Return help.
            self._create_file(content_dir, "SummaryHub.xml", "<summary>")
            help_path = os.path.join(tmp_dir, "en-US", "SummaryHub.xml")

            assert _get_help_args_for_screen(DisplayModes.GUI, "installation-summary") == \
                HelpArguments(help_path, "SummaryHub.xml", "")

            # Return help with anchor.
            self._create_file(content_dir, "UserSpoke.xml", "<user>")
            help_path = os.path.join(tmp_dir, "en-US", "UserSpoke.xml")

            assert _get_help_args_for_screen(DisplayModes.GUI, "user-configuration") == \
                HelpArguments(help_path, "UserSpoke.xml", "create-user")

    @patch('pyanaconda.ui.lib.help.startProgram')
    def test_show_graphical_help(self, starter):
        """Test the show_graphical_help function."""
        show_graphical_help("/my/file")
        starter.assert_called_once_with(["yelp", "/my/file"], reset_lang=False)
        starter.reset_mock()

        show_graphical_help("/my/file", "my-anchor")
        starter.assert_called_once_with(["yelp", "ghelp:/my/file?my-anchor"], reset_lang=False)
        starter.reset_mock()

        show_graphical_help("")
        starter.assert_not_called()

    @patch('pyanaconda.ui.lib.help.conf')
    def test_get_help_path_for_screen(self, conf_mock):
        """Test the get_help_path_for_screen function."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            conf_mock.ui.help_directory = tmp_dir
            content_dir = os.path.join(tmp_dir, "en-US")

            # No help.
            _get_help_mapping.cache_clear()
            self._create_file(tmp_dir, "anaconda-tui.json", TUI_MAPPING)
            assert get_help_path_for_screen("installation-summary") is None

            # Help file.
            self._create_file(content_dir, "SummaryHub.txt", "<summary>")
            self._create_file(content_dir, "UserSpoke.txt", "<user>")

            assert get_help_path_for_screen("installation-summary") == \
                os.path.join(tmp_dir, "en-US", "SummaryHub.txt")

            assert get_help_path_for_screen("user-configuration") == \
                os.path.join(tmp_dir, "en-US", "UserSpoke.txt")

    @patch('pyanaconda.ui.lib.help.startProgram')
    @patch('pyanaconda.ui.lib.help.conf')
    def test_show_graphical_help_for_screen(self, conf_mock, starter):
        with tempfile.TemporaryDirectory() as tmp_dir:
            conf_mock.ui.help_directory = tmp_dir
            content_dir = os.path.join(tmp_dir, "en-US")

            # No help.
            _get_help_mapping.cache_clear()
            self._create_file(tmp_dir, "anaconda-gui.json", GUI_MAPPING)

            show_graphical_help_for_screen("installation-summary")
            starter.assert_not_called()
            starter.reset_mock()

            # Help file.
            self._create_file(content_dir, "SummaryHub.xml", "<summary>")
            show_graphical_help_for_screen("installation-summary")

            help_path = os.path.join(tmp_dir, "en-US", "SummaryHub.xml")
            starter.assert_called_once_with(["yelp", help_path], reset_lang=False)
            starter.reset_mock()

            # Help file with anchor.
            self._create_file(content_dir, "UserSpoke.xml", "<create-user>")
            show_graphical_help_for_screen("user-configuration")

            help_path = os.path.join(tmp_dir, "en-US", "UserSpoke.xml")
            yelp_arg = "ghelp:" + help_path + "?create-user"
            starter.assert_called_once_with(["yelp", yelp_arg], reset_lang=False)
