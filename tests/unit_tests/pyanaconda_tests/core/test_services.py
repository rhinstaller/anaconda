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
import unittest
from unittest.mock import patch
from pyanaconda.core import service


class RunSystemctlTests(unittest.TestCase):

    def test_is_service_installed(self):
        """Test the is_service_installed function."""
        with patch('pyanaconda.core.service.execWithCapture') as execute:
            execute.return_value = "fake.service enabled enabled"
            assert service.is_service_installed("fake") is True
            execute.assert_called_once_with("systemctl", [
                "list-unit-files", "fake.service", "--no-legend", "--root", "/mnt/sysroot"
            ])

        with patch('pyanaconda.core.service.execWithCapture') as execute:
            execute.return_value = "fake.service enabled enabled"
            assert service.is_service_installed("fake.service", root="/") == True
            execute.assert_called_once_with("systemctl", [
                "list-unit-files", "fake.service", "--no-legend"
            ])

        with patch('pyanaconda.core.service.execWithCapture') as execute:
            execute.return_value = ""
            assert service.is_service_installed("fake", root="/") == False
            execute.assert_called_once_with("systemctl", [
                "list-unit-files", "fake.service", "--no-legend"
            ])
