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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Martin Kolman <mkolman@redhat.com>
#
import os
import tempfile
import json

import unittest
from unittest.mock import patch

from pyanaconda.ui.lib.help import get_help_id_mapping, HELP_ID_MAPPING_FILE_NAME, \
    get_best_help_file, get_default_help_file


class HelpSystemTestCase(unittest.TestCase):
    """Test the built in help system."""

    def help_id_mapping_no_file_test(self):
        """Test help id to anchor mapping file loading - no file."""
        with tempfile.TemporaryDirectory() as tempdir:
            # check help_id_mapping was parsed correctly
            # when the mapping file is missing
            self.assertEqual(get_help_id_mapping(tempdir), {})

    def help_id_mapping_valid_file_test(self):
        """Test help id to anchor mapping file loading - valid file."""

        with tempfile.TemporaryDirectory() as tempdir:
            # write an anchors file to the tempdir
            anchors_mapping_dict = {
                "SoftwareSelectionSpoke":
                "configuring-software-selection_configuring-software-settings",
                "SubscriptionSpoke":
                "connect-to-red-hat_configuring-system-settings",
                "ProgressHub":
                "final-installer-configuration_graphical-installation",
            }
            anchors_file_path = os.path.join(tempdir, HELP_ID_MAPPING_FILE_NAME)
            with open(anchors_file_path, "wt") as f:
                f.write(json.dumps(anchors_mapping_dict))
            # check help_id_mapping was parsed correctly
            self.assertEqual(get_help_id_mapping(tempdir), anchors_mapping_dict)

    def help_id_mapping_file_not_valid_test(self):
        """Test help id to anchor mapping file loading - file not valid."""

        with tempfile.TemporaryDirectory() as tempdir:
            # write something that is not valid json to the mapping file
            anchors_file_path = os.path.join(tempdir, HELP_ID_MAPPING_FILE_NAME)
            with open(anchors_file_path, "wt") as f:
                f.write("foo")
            # check help_id_mapping was not parsed correctly and the dict is empty
            self.assertEqual(get_help_id_mapping(tempdir), {})

    def get_best_help_file_no_help_file_test(self):
        """Test get_best_help_file() - no help file."""
        with tempfile.TemporaryDirectory() as tempdir:
            # should return None if no help file is found
            self.assertIsNone(get_best_help_file(tempdir, "foo.xml"))

    @patch("os.environ.get", return_value="cs_CZ")
    def get_best_help_file_locale_available_help_test(self, environ_get):
        """Test get_best_help_file() - current(Czech) locale available."""
        with tempfile.TemporaryDirectory() as tempdir:
            os.mkdir(os.path.join(tempdir, "en-US"))
            os.mknod(os.path.join(tempdir, "en-US", "foo.xml"))
            os.mkdir(os.path.join(tempdir, "cs-CZ"))
            os.mknod(os.path.join(tempdir, "cs-CZ", "foo.xml"))
            self.assertEqual(get_best_help_file(tempdir, "foo.xml"),
                             os.path.join(tempdir, "cs-CZ", "foo.xml"))

    @patch("os.environ.get", return_value="cs_CZ")
    def get_best_help_file_english_help_test(self, environ_get):
        """Test get_best_help_file() - English help available."""
        with tempfile.TemporaryDirectory() as tempdir:
            os.mkdir(os.path.join(tempdir, "en-US"))
            os.mknod(os.path.join(tempdir, "en-US", "foo.xml"))
            self.assertEqual(get_best_help_file(tempdir, "foo.xml"),
                             os.path.join(tempdir, "en-US", "foo.xml"))

    @patch("os.environ.get", return_value="cs_CZ")
    def get_best_help_file_current_locale_available(self, environ_get):
        """Test get_best_help_file() - current locale and fallback locale not available."""
        # content for the current locale (Czech for this test) and fallback
        # locale (English) not available
        with tempfile.TemporaryDirectory() as tempdir:
            os.mkdir(os.path.join(tempdir, "de-DE"))
            os.mknod(os.path.join(tempdir, "de-DE", "foo.xml"))
            self.assertEqual(get_best_help_file(tempdir, "foo.xml"), None)

    @patch('pyanaconda.ui.lib.help.conf')
    @patch("pyanaconda.ui.lib.help.get_best_help_file")
    def get_default_help_file_test(self, get_best_help_file_mock, conf):
        """Test get_default_help_file()."""
        conf.ui.help_directory = "foo_dir"
        conf.system.provides_web_browser = False
        conf.ui.default_help_pages = ["foo.txt", "foo.xml", "foo_live.xml"]
        get_best_help_file_mock.return_value = "foo"
        self.assertEqual(get_default_help_file(plain_text=False), "foo")
        get_best_help_file_mock.assert_called_with("foo_dir", "foo.xml")

    @patch('pyanaconda.ui.lib.help.conf')
    @patch("pyanaconda.ui.lib.help.get_best_help_file")
    def get_default_help_file_plain_text_test(self, get_best_help_file_mock, conf):
        """Test get_default_help_file() - plain text."""
        conf.ui.help_directory = "foo_dir"
        conf.system.provides_web_browser = False
        conf.ui.default_help_pages = ["foo.txt", "foo.xml", "foo_live.xml"]
        get_best_help_file_mock.return_value = "foo"
        self.assertEqual(get_default_help_file(plain_text=True), "foo")
        get_best_help_file_mock.assert_called_with("foo_dir", "foo.txt")

    @patch('pyanaconda.ui.lib.help.conf')
    @patch("pyanaconda.ui.lib.help.get_best_help_file")
    def get_default_help_file_web_browser_available_test(self, get_best_help_file_mock, conf):
        """Test get_default_help_file() - web browser available."""
        conf.ui.help_directory = "foo_dir"
        conf.system.provides_web_browser = True
        conf.ui.default_help_pages = ["foo.txt", "foo.xml", "foo_live.xml"]
        get_best_help_file_mock.return_value = "foo"
        self.assertEqual(get_default_help_file(plain_text=False), "foo")
        get_best_help_file_mock.assert_called_with("foo_dir", "foo_live.xml")

    @patch('pyanaconda.ui.lib.help.conf')
    @patch("pyanaconda.ui.lib.help.get_best_help_file")
    def get_placeholder_not_found_test(self, get_best_help_file_mock, conf):
        """Test get_default_help_file() - placeholder not found."""
        conf.ui.help_directory = "foo_dir"
        conf.system.provides_web_browser = False
        conf.ui.default_help_pages = ["foo.txt", "foo.xml", "foo_live.xml"]
        get_best_help_file_mock.return_value = None
        self.assertEqual(get_default_help_file(plain_text=False), None)
        get_best_help_file_mock.assert_called_with("foo_dir", "foo.xml")
