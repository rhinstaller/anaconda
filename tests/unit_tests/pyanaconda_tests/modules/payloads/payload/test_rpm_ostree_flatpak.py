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
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest

from pyanaconda.modules.common.errors.installation import PayloadInstallationError
from pyanaconda.modules.payloads.payload.rpm_ostree.flatpak_installation import (
    InstallFlatpaksTask,
)


class InstallFlatpakTaskTest(unittest.TestCase):
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.flatpak_installation.FlatpakManager")
    def test_run_success(self, fm_mock):
        """Test InstallFlatpakTask.run success"""
        fm_instance = fm_mock.return_value

        with TemporaryDirectory() as temp:
            task = InstallFlatpaksTask(temp)
            task.run()

        fm_instance.install_all.assert_called_once()
        fm_instance.add_remote.assert_called_once()
        fm_instance.remove_remote.assert_called_once()

    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.flatpak_installation.FlatpakManager")
    def test_run_failure(self, fm_mock):
        """Test InstallFlatpakTask.run failure"""
        fm_instance = fm_mock.return_value
        fm_instance.install_all.side_effect = PayloadInstallationError

        with TemporaryDirectory() as temp:
            with pytest.raises(PayloadInstallationError):
                task = InstallFlatpaksTask(temp)
                task.run()
