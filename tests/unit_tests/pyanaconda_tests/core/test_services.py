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

import pytest

from pyanaconda.core import service


class RunSystemctlTests(unittest.TestCase):

    @patch('pyanaconda.core.service.execWithRedirect')
    def test_start_service(self, exec_mock):
        """Test start_service"""
        service.start_service("something")
        exec_mock.assert_called_once_with("systemctl", ["start", "something"])

    @patch('pyanaconda.core.service.execWithRedirect')
    def test_stop_service(self, exec_mock):
        """Test stop_service"""
        service.stop_service("something")
        exec_mock.assert_called_once_with("systemctl", ["stop", "something"])

    @patch('pyanaconda.core.service.execWithRedirect')
    def test_restart_service(self, exec_mock):
        """Test restart_service"""
        service.restart_service("something")
        exec_mock.assert_called_once_with("systemctl", ["restart", "something"])

    @patch('pyanaconda.core.service.execWithRedirect')
    def test_is_service_running(self, exec_mock):
        """Test is_service_running"""
        exec_mock.return_value = 0
        assert service.is_service_running("something")
        exec_mock.assert_called_once_with("systemctl", ["status", "something"])

        exec_mock.reset_mock()
        exec_mock.return_value = 1
        assert not service.is_service_running("something")
        exec_mock.assert_called_once_with("systemctl", ["status", "something"])

    @patch('pyanaconda.core.service.execWithCapture')
    def test_is_service_installed(self, exec_mock):
        """Test the is_service_installed function."""
        # default root value
        exec_mock.return_value = "fake.service enabled enabled"
        assert service.is_service_installed("fake")
        exec_mock.assert_called_once_with("systemctl", [
            "list-unit-files", "fake.service", "--no-legend"
        ])

        # root in inst.env.
        exec_mock.reset_mock()
        exec_mock.return_value = "fake.service enabled enabled"
        assert service.is_service_installed("fake.service", root="/")
        exec_mock.assert_called_once_with("systemctl", [
            "list-unit-files", "fake.service", "--no-legend"
        ])

        # other root
        exec_mock.reset_mock()
        exec_mock.return_value = "fake.service enabled enabled"
        assert service.is_service_installed("fake.service", root="/somewhere")
        exec_mock.assert_called_once_with("systemctl", [
            "list-unit-files", "fake.service", "--no-legend", "--root", "/somewhere"
        ])

        # empty call result
        exec_mock.reset_mock()
        exec_mock.return_value = ""
        assert not service.is_service_installed("fake", root="/")
        exec_mock.assert_called_once_with("systemctl", [
            "list-unit-files", "fake.service", "--no-legend"
        ])

    @patch('pyanaconda.core.service.execWithRedirect', return_value=0)
    def test_enable_service(self, exec_mock):
        """Test enable_service"""
        # root in inst.env.
        service.enable_service("frobnicatord", root="/")
        exec_mock.assert_called_once_with("systemctl", ["enable", "frobnicatord"])

        # root elsewhere
        exec_mock.reset_mock()
        service.enable_service("frobnicatord", root="/somewhere")
        exec_mock.assert_called_once_with("systemctl",
                                          ["enable", "frobnicatord", "--root", "/somewhere"])

        # default root value
        exec_mock.reset_mock()
        service.enable_service("frobnicatord")
        exec_mock.assert_called_once_with("systemctl", ["enable", "frobnicatord"])

        # nonzero return code
        exec_mock.reset_mock()
        exec_mock.return_value = 255
        with pytest.raises(ValueError):
            service.enable_service("frobnicatord", root="/")
        exec_mock.assert_called_once_with("systemctl", ["enable", "frobnicatord"])

    @patch('pyanaconda.core.service.execWithRedirect')
    def test_disable_service(self, exec_mock):
        """Test disable_service"""
        # root in inst.env.
        service.disable_service("frobnicatord", root="/")
        exec_mock.assert_called_once_with("systemctl", ["disable", "frobnicatord"])

        # other root
        exec_mock.reset_mock()
        service.disable_service("frobnicatord", root="/somewhere")
        exec_mock.assert_called_once_with("systemctl",
                                          ["disable", "frobnicatord", "--root", "/somewhere"])

        # default root value
        exec_mock.reset_mock()
        service.disable_service("frobnicatord")
        exec_mock.assert_called_once_with("systemctl", ["disable", "frobnicatord"])

        # must not fail on nonzero return code
        exec_mock.reset_mock()
        exec_mock.return_value = 255
        service.disable_service("frobnicatord", root="/")
        exec_mock.assert_called_once_with("systemctl", ["disable", "frobnicatord"])
