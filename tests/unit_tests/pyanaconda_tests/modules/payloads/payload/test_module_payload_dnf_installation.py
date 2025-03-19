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

from unittest.mock import patch, call

from pyanaconda.core.constants import RPM_LANGUAGES_NONE, MULTILIB_POLICY_ALL
from pyanaconda.core.util import join_paths
from pyanaconda.modules.common.structures.payload import PackagesConfigurationData
from pyanaconda.modules.payloads.payload.dnf.installation import ImportRPMKeysTask, \
    SetRPMMacrosTask, UpdateDNFConfigurationTask


class SetRPMMacrosTaskTestCase(unittest.TestCase):
    """Test the installation task for setting the RPM macros."""

    def _run_task(self, data):
        """Run the installation task."""
        task = SetRPMMacrosTask(data)
        task.run()
        return task

    def _check_macros(self, task, mock_rpm, expected_macros):
        """Check that the expected macros are set up."""
        assert task._macros == expected_macros

        calls = [call(*macro) for macro in expected_macros]
        mock_rpm.addMacro.assert_has_calls(calls)

    @patch("pyanaconda.modules.payloads.payload.dnf.installation.rpm")
    def test_set_rpm_macros_default(self, mock_rpm):
        data = PackagesConfigurationData()

        macros = [
            ('__dbi_htconfig', 'hash nofsync %{__dbi_other} %{__dbi_perms}'),
            ('__file_context_path', '/etc/selinux/targeted/contexts/files/file_contexts')
        ]

        task = self._run_task(data)
        self._check_macros(task, mock_rpm, macros)

    @patch("pyanaconda.modules.payloads.payload.dnf.installation.rpm")
    def test_set_rpm_macros_exclude_docs(self, mock_rpm):
        data = PackagesConfigurationData()
        data.docs_excluded = True

        macros = [
            ('__dbi_htconfig', 'hash nofsync %{__dbi_other} %{__dbi_perms}'),
            ('_excludedocs', '1'),
            ('__file_context_path', '/etc/selinux/targeted/contexts/files/file_contexts')
        ]

        task = self._run_task(data)
        self._check_macros(task, mock_rpm, macros)

    @patch("pyanaconda.modules.payloads.payload.dnf.installation.rpm")
    def test_set_rpm_macros_install_langs(self, mock_rpm):
        data = PackagesConfigurationData()
        data.languages = "en,es"

        macros = [
            ('__dbi_htconfig', 'hash nofsync %{__dbi_other} %{__dbi_perms}'),
            ('_install_langs', 'en,es'),
            ('__file_context_path', '/etc/selinux/targeted/contexts/files/file_contexts')
        ]

        task = self._run_task(data)
        self._check_macros(task, mock_rpm, macros)

    @patch("pyanaconda.modules.payloads.payload.dnf.installation.rpm")
    def test_set_rpm_macros_no_install_langs(self, mock_rpm):
        data = PackagesConfigurationData()
        data.languages = RPM_LANGUAGES_NONE

        macros = [
            ('__dbi_htconfig', 'hash nofsync %{__dbi_other} %{__dbi_perms}'),
            ('_install_langs', '%{nil}'),
            ('__file_context_path', '/etc/selinux/targeted/contexts/files/file_contexts')
        ]

        task = self._run_task(data)
        self._check_macros(task, mock_rpm, macros)

    @patch("pyanaconda.modules.payloads.payload.dnf.installation.os")
    @patch("pyanaconda.modules.payloads.payload.dnf.installation.rpm")
    def test_set_rpm_macros_selinux(self, mock_rpm, mock_os):
        mock_os.access.return_value = True
        data = PackagesConfigurationData()

        macros = [
            ('__dbi_htconfig', 'hash nofsync %{__dbi_other} %{__dbi_perms}'),
            ('__file_context_path', '/etc/selinux/targeted/contexts/files/file_contexts'),
        ]

        task = self._run_task(data)
        self._check_macros(task, mock_rpm, macros)

    @patch("pyanaconda.modules.payloads.payload.dnf.installation.conf")
    @patch("pyanaconda.modules.payloads.payload.dnf.installation.rpm")
    def test_set_rpm_macros_selinux_disabled(self, mock_rpm, mock_conf):
        mock_conf.security.selinux = 0
        data = PackagesConfigurationData()

        macros = [
            ('__dbi_htconfig', 'hash nofsync %{__dbi_other} %{__dbi_perms}'),
            ('__file_context_path', '%{nil}'),
        ]

        task = self._run_task(data)
        self._check_macros(task, mock_rpm, macros)


class ImportRPMKeysTaskTestCase(unittest.TestCase):

    def _create_rpm(self, sysroot):
        """Create /usr/bin/rpm in the given system root."""
        os.makedirs(join_paths(sysroot, "/usr/bin"))
        os.mknod(join_paths(sysroot, "/usr/bin/rpm"))

    def test_import_no_keys(self):
        """Import no GPG keys."""
        with tempfile.TemporaryDirectory() as sysroot:
            task = ImportRPMKeysTask(sysroot, [])

            with self.assertLogs(level="DEBUG") as cm:
                task.run()

            msg = "No GPG keys to import."
            assert any(map(lambda x: msg in x, cm.output))

    def test_import_no_rpm(self):
        """Import GPG keys without installed rpm."""
        with tempfile.TemporaryDirectory() as sysroot:
            task = ImportRPMKeysTask(sysroot, ["key"])

            with self.assertLogs(level="DEBUG") as cm:
                task.run()

            msg = "Can not import GPG keys to RPM database"
            assert any(map(lambda x: msg in x, cm.output))

    @patch("pyanaconda.modules.payloads.payload.dnf.installation.util.execWithRedirect")
    def test_import_error(self, mock_exec):
        """Import GPG keys with error."""
        mock_exec.return_value = 1

        with tempfile.TemporaryDirectory() as sysroot:
            self._create_rpm(sysroot)
            task = ImportRPMKeysTask(sysroot, ["key"])

            with self.assertLogs(level="ERROR") as cm:
                task.run()

            msg = "Failed to import the GPG key."
            assert any(map(lambda x: msg in x, cm.output))

    @patch("pyanaconda.modules.payloads.payload.dnf.installation.util.execWithRedirect")
    def test_import_keys(self, mock_exec):
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
    def test_import_substitution(self, mock_util):
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


class UpdateDNFConfigurationTaskTestCase(unittest.TestCase):
    """Test the UpdateDNFConfigurationTask class."""

    @patch("pyanaconda.core.util.execWithRedirect")
    def test_no_update(self, execute):
        """Don't update the DNF configuration."""
        with tempfile.TemporaryDirectory() as sysroot:
            data = PackagesConfigurationData()

            task = UpdateDNFConfigurationTask(sysroot, data)
            task.run()

            execute.assert_not_called()

    @patch("pyanaconda.core.util.execWithRedirect")
    def test_failed_update(self, execute):
        """The update of the DNF configuration has failed."""
        execute.return_value = 1

        with tempfile.TemporaryDirectory() as sysroot:
            data = PackagesConfigurationData()
            data.multilib_policy = MULTILIB_POLICY_ALL

            task = UpdateDNFConfigurationTask(sysroot, data)

            with self.assertLogs(level="WARNING") as cm:
                task.run()

            msg = "Failed to update the DNF configuration (1)."
            assert any(map(lambda x: msg in x, cm.output))

    @patch("pyanaconda.core.util.execWithRedirect")
    def test_error_update(self, execute):
        """The update of the DNF configuration has failed."""
        execute.side_effect = OSError("Fake!")

        with tempfile.TemporaryDirectory() as sysroot:
            data = PackagesConfigurationData()
            data.multilib_policy = MULTILIB_POLICY_ALL

            task = UpdateDNFConfigurationTask(sysroot, data)

            with self.assertLogs(level="WARNING") as cm:
                task.run()

            msg = "Couldn't update the DNF configuration: Fake!"
            assert any(map(lambda x: msg in x, cm.output))

    @patch("pyanaconda.core.util.execWithRedirect")
    def test_multilib_policy(self, execute):
        """Update the multilib policy."""
        execute.return_value = 0

        with tempfile.TemporaryDirectory() as sysroot:
            data = PackagesConfigurationData()
            data.multilib_policy = MULTILIB_POLICY_ALL

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
