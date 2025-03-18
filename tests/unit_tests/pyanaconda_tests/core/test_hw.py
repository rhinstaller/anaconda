# -*- coding: utf-8 -*-
#
# Copyright (C) 2013  Red Hat, Inc.
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

import unittest
from unittest.mock import patch
from textwrap import dedent
from io import StringIO

from pyanaconda.core.hw import is_lpae_available, detect_virtualized_platform, is_smt_enabled


class MiscHwUtilsTests(unittest.TestCase):

    @patch("pyanaconda.core.hw.execWithCapture")
    def test_detect_virtualized_platform(self, exec_mock):
        """Test the function detect_virtualized_platform."""
        exec_mock.side_effect = OSError
        assert detect_virtualized_platform() is None

        exec_mock.side_effect = ["none"]
        assert detect_virtualized_platform() is None

        exec_mock.side_effect = ["vmware"]
        assert detect_virtualized_platform() == "vmware"

    @patch("pyanaconda.core.hw.open")
    @patch("pyanaconda.core.hw.is_arm")
    def test_is_lpae_available(self, is_arm, mock_open):
        """Test the is_lpae_available function."""
        is_arm.return_value = False
        assert is_lpae_available() is False

        is_arm.return_value = True
        cpu_info = """
        processor       : 0
        model name      : ARMv7 Processor rev 2 (v7l)
        BogoMIPS        : 50.00
        Features        : half thumb fastmult vfp edsp thumbee vfpv3 tls idiva idivt vfpd32
        CPU implementer : 0x56
        CPU architecture: 7
        CPU variant     : 0x2
        CPU part        : 0x584
        CPU revision    : 2
        """

        mock_open.return_value = StringIO(dedent(cpu_info))
        assert is_lpae_available() is False

        cpu_info = """
        processor       : 0
        model name      : ARMv7 Processor rev 2 (v7l)
        BogoMIPS        : 50.00
        Features        : half thumb fastmult vfp edsp thumbee vfpv3 tls idiva idivt vfpd32 lpae
        CPU implementer : 0x56
        CPU architecture: 7
        CPU variant     : 0x2
        CPU part        : 0x584
        CPU revision    : 2
        """

        mock_open.return_value = StringIO(dedent(cpu_info))
        assert is_lpae_available() is True

    @patch("pyanaconda.flags.flags")
    @patch("pyanaconda.core.configuration.anaconda.conf")
    @patch("pyanaconda.core.hw.open")
    def test_is_smt_enabled(self, open_mock, conf, flags):
        """Test is_smt_enabled function"""

        # all combinations of flags and conf that prevent execution
        flags.automatedInstall = True
        for is_hw in (True, False):
            for smt_on in (True, False):
                conf.target.is_hardware = is_hw
                conf.system.can_detect_enabled_smt = smt_on
                assert is_smt_enabled() is False
        open_mock.assert_not_called()

        conf.target.is_hardware = False
        for auto_inst in (True, False):
            for smt_on in (True, False):
                flags.automatedInstall = auto_inst
                conf.system.can_detect_enabled_smt = smt_on
                assert is_smt_enabled() is False
        open_mock.assert_not_called()

        conf.system.can_detect_enabled_smt = False
        for auto_inst in (True, False):
            for is_hw in (True, False):
                flags.automatedInstall = auto_inst
                conf.target.is_hardware = is_hw
                assert is_smt_enabled() is False
        open_mock.assert_not_called()

        # for the rest, keep the combination that allows actual hw check
        flags.automatedInstall = False
        conf.target.is_hardware = True
        conf.system.can_detect_enabled_smt = True

        # diverse values to try
        test_combinations = (
            ("1", True),
            ("  1 \n", True),
            ("0", False),
            ("fdsfdsafsa", False),
            ("256", False),
            ("\n", False)
        )
        for f_input, f_output in test_combinations:
            open_mock.reset_mock()
            open_mock.return_value = StringIO(f_input)
            assert is_smt_enabled() is f_output
            open_mock.assert_called_once_with("/sys/devices/system/cpu/smt/active")

        # failed to open the "file"
        open_mock.reset_mock()
        open_mock.side_effect = OSError
        assert is_smt_enabled() is False
        open_mock.assert_called_once_with("/sys/devices/system/cpu/smt/active")
