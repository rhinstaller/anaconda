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
import tempfile
import unittest

from unittest.mock import patch

from pyanaconda.kickstart import AnacondaKSHandler
from pyanaconda.modules.payloads.payload.dnf.installation import UpdateDNFConfigurationTask


class UpdateDNFConfigurationTaskTestCase(unittest.TestCase):
    """Test the UpdateDNFConfigurationTask class."""

    @patch("pyanaconda.core.util.execWithRedirect")
    def test_no_update(self, execute):
        """Don't update the DNF configuration."""
        with tempfile.TemporaryDirectory() as sysroot:
            data = AnacondaKSHandler()

            task = UpdateDNFConfigurationTask(sysroot, data)
            task.run()

            execute.assert_not_called()

    @patch("pyanaconda.core.util.execWithRedirect")
    def test_failed_update(self, execute):
        """The update of the DNF configuration has failed."""
        execute.return_value = 1

        with tempfile.TemporaryDirectory() as sysroot:
            data = AnacondaKSHandler()
            data.packages.multiLib = True

            task = UpdateDNFConfigurationTask(sysroot, data)

            with self.assertLogs(level="WARNING") as cm:
                task.run()

            msg = "Failed to update the DNF configuration (1)."
            self.assertTrue(any(map(lambda x: msg in x, cm.output)))

    @patch("pyanaconda.core.util.execWithRedirect")
    def test_error_update(self, execute):
        """The update of the DNF configuration has failed."""
        execute.side_effect = OSError("Fake!")

        with tempfile.TemporaryDirectory() as sysroot:
            data = AnacondaKSHandler()
            data.packages.multiLib = True

            task = UpdateDNFConfigurationTask(sysroot, data)

            with self.assertLogs(level="WARNING") as cm:
                task.run()

            msg = "Couldn't update the DNF configuration: Fake!"
            self.assertTrue(any(map(lambda x: msg in x, cm.output)))

    @patch("pyanaconda.core.util.execWithRedirect")
    def test_multilib_policy(self, execute):
        """Update the multilib policy."""
        execute.return_value = 0

        with tempfile.TemporaryDirectory() as sysroot:
            data = AnacondaKSHandler()
            data.packages.multiLib = True

            task = UpdateDNFConfigurationTask(sysroot, data)
            task.run()

            execute.assert_called_once_with(
                "dnf",
                [
                    "config-manager",
                    "--save",
                    "--setopt=multilib_policy=all",
                ],
                root=sysroot
            )
