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

import unittest

from unittest.mock import patch, mock_open, Mock
from textwrap import dedent

from pyanaconda.startup_utils import print_dracut_errors


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
