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
import os
import tempfile
import unittest
from unittest.mock import patch, call

from pyanaconda.core.util import join_paths
from pyanaconda.modules.payloads.payload.dnf.installation import ImportRPMKeysTask


class ImportRPMKeysTaskTestCase(unittest.TestCase):

    def _create_rpm(self, sysroot):
        """Create /usr/bin/rpm in the given system root."""
        os.makedirs(join_paths(sysroot, "/usr/bin"))
        os.mknod(join_paths(sysroot, "/usr/bin/rpm"))

    def import_no_keys_test(self):
        """Import no GPG keys."""
        with tempfile.TemporaryDirectory() as sysroot:
            task = ImportRPMKeysTask(sysroot, [])

            with self.assertLogs(level="DEBUG") as cm:
                task.run()

            msg = "No GPG keys to import."
            self.assertTrue(any(map(lambda x: msg in x, cm.output)))

    def import_no_rpm_test(self):
        """Import GPG keys without installed rpm."""
        with tempfile.TemporaryDirectory() as sysroot:
            task = ImportRPMKeysTask(sysroot, ["key"])

            with self.assertLogs(level="DEBUG") as cm:
                task.run()

            msg = "Can not import GPG keys to RPM database"
            self.assertTrue(any(map(lambda x: msg in x, cm.output)))

    @patch("pyanaconda.modules.payloads.payload.dnf.installation.util.execWithRedirect")
    def import_error_test(self, mock_exec):
        """Import GPG keys with error."""
        mock_exec.return_value = 1

        with tempfile.TemporaryDirectory() as sysroot:
            self._create_rpm(sysroot)
            task = ImportRPMKeysTask(sysroot, ["key"])

            with self.assertLogs(level="ERROR") as cm:
                task.run()

            msg = "Failed to import the GPG key."
            self.assertTrue(any(map(lambda x: msg in x, cm.output)))

    @patch("pyanaconda.modules.payloads.payload.dnf.installation.util.execWithRedirect")
    def import_keys_test(self, mock_exec):
        """Import GPG keys."""
        mock_exec.return_value = 0

        key_1 = "/etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-1"
        key_2 = "/etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-2"

        with tempfile.TemporaryDirectory() as sysroot:
            self._create_rpm(sysroot)

            task = ImportRPMKeysTask(sysroot, [key_1, key_2])
            task.run()

            mock_exec.assert_has_calls([
                call("rpm", ["--import", key_1], root=sysroot),
                call("rpm", ["--import", key_2], root=sysroot),
            ])

    @patch("pyanaconda.modules.payloads.payload.dnf.installation.util")
    def import_substitution_test(self, mock_util):
        """Import GPG keys with variables."""
        mock_util.execWithRedirect.return_value = 0
        mock_util.execWithCapture.return_value = "s390x"
        mock_util.get_os_release_value.return_value = "34"

        key = "/etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-$releasever-$basearch"

        with tempfile.TemporaryDirectory() as sysroot:
            self._create_rpm(sysroot)

            task = ImportRPMKeysTask(sysroot, [key])
            task.run()

            mock_util.execWithRedirect.assert_called_once_with(
                "rpm",
                ["--import", "/etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-34-s390x"],
                root=sysroot
            )
