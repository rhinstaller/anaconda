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

from unittest.mock import patch, call, Mock

from pyanaconda.core.constants import RPM_LANGUAGES_NONE
from pyanaconda.core.util import join_paths
from pyanaconda.modules.common.errors.installation import NonCriticalInstallationError, \
    PayloadInstallationError
from pyanaconda.modules.common.structures.packages import PackagesConfigurationData, \
    PackagesSelectionData
from pyanaconda.modules.common.structures.requirement import Requirement
from pyanaconda.modules.payloads.payload.dnf.dnf_manager import DNFManager, MissingSpecsError, \
    BrokenSpecsError, InvalidSelectionError
from pyanaconda.modules.payloads.payload.dnf.installation import ImportRPMKeysTask, \
    SetRPMMacrosTask, DownloadPackagesTask, InstallPackagesTask, PrepareDownloadLocationTask, \
    CleanUpDownloadLocationTask, ResolvePackagesTask


class SetRPMMacrosTaskTestCase(unittest.TestCase):
    """Test the installation task for setting the RPM macros."""

    def _run_task(self, data):
        """Run the installation task."""
        task = SetRPMMacrosTask(data)
        task.run()
        return task

    def _check_macros(self, task, mock_rpm, expected_macros):
        """Check that the expected macros are set up."""
        self.assertEqual(task._macros, expected_macros)

        calls = [call(*macro) for macro in expected_macros]
        mock_rpm.addMacro.assert_has_calls(calls)

    @patch("pyanaconda.modules.payloads.payload.dnf.installation.rpm")
    def set_rpm_macros_default_test(self, mock_rpm):
        data = PackagesConfigurationData()

        macros = [
            ('__dbi_htconfig', 'hash nofsync %{__dbi_other} %{__dbi_perms}')
        ]

        task = self._run_task(data)
        self._check_macros(task, mock_rpm, macros)

    @patch("pyanaconda.modules.payloads.payload.dnf.installation.rpm")
    def set_rpm_macros_exclude_docs_test(self, mock_rpm):
        data = PackagesConfigurationData()
        data.docs_excluded = True

        macros = [
            ('__dbi_htconfig', 'hash nofsync %{__dbi_other} %{__dbi_perms}'),
            ('_excludedocs', '1'),
        ]

        task = self._run_task(data)
        self._check_macros(task, mock_rpm, macros)

    @patch("pyanaconda.modules.payloads.payload.dnf.installation.rpm")
    def set_rpm_macros_install_langs_test(self, mock_rpm):
        data = PackagesConfigurationData()
        data.languages = "en,es"

        macros = [
            ('__dbi_htconfig', 'hash nofsync %{__dbi_other} %{__dbi_perms}'),
            ('_install_langs', 'en,es'),
        ]

        task = self._run_task(data)
        self._check_macros(task, mock_rpm, macros)

    @patch("pyanaconda.modules.payloads.payload.dnf.installation.rpm")
    def set_rpm_macros_no_install_langs_test(self, mock_rpm):
        data = PackagesConfigurationData()
        data.languages = RPM_LANGUAGES_NONE

        macros = [
            ('__dbi_htconfig', 'hash nofsync %{__dbi_other} %{__dbi_perms}'),
            ('_install_langs', '%{nil}'),
        ]

        task = self._run_task(data)
        self._check_macros(task, mock_rpm, macros)

    @patch("pyanaconda.modules.payloads.payload.dnf.installation.os")
    @patch("pyanaconda.modules.payloads.payload.dnf.installation.rpm")
    def set_rpm_macros_selinux_test(self, mock_rpm, mock_os):
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
    def set_rpm_macros_selinux_disabled_test(self, mock_rpm, mock_conf):
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


class DownloadPackagesTaskTestCase(unittest.TestCase):

    def run_test(self):
        """Run the DownloadPackagesTask class."""
        callback = Mock()

        dnf_manager = Mock()
        dnf_manager.download_packages.side_effect = self._download_packages

        task = DownloadPackagesTask(dnf_manager)
        task.progress_changed_signal.connect(callback)
        task.run()

        self.assertEqual(task.name, "Download packages")
        dnf_manager.download_packages.assert_called_once_with(task.report_progress)

        callback.assert_has_calls([
            call(0, "Downloading packages"),
            call(0, "Downloaded 0%"),
            call(0, "Downloaded 50%"),
            call(0, "Downloaded 100%"),
        ])

    def _download_packages(self, callback):
        """Simulate the download of packages."""
        callback("Downloaded 0%")
        callback("Downloaded 50%")
        callback("Downloaded 100%")


class InstallPackagesTaskTestCase(unittest.TestCase):

    def run_test(self):
        """Run the InstallPackagesTask class."""
        callback = Mock()

        dnf_manager = Mock()
        dnf_manager.install_packages.side_effect = self._install_packages

        task = InstallPackagesTask(dnf_manager)
        task.progress_changed_signal.connect(callback)
        task.run()

        self.assertEqual(task.name, "Install packages")
        dnf_manager.install_packages.assert_called_once_with(task.report_progress)

        callback.assert_has_calls([
            call(0, "Preparing transaction from installation source"),
            call(0, "Installing p1"),
            call(0, "Installing p2"),
            call(0, "Installing p3"),
        ])

    def _install_packages(self, callback):
        """Simulate the installation of packages."""
        callback("Installing p1")
        callback("Installing p2")
        callback("Installing p3")


class PrepareDownloadLocationTaskTestCase(unittest.TestCase):

    @patch("pyanaconda.modules.payloads.payload.dnf.installation.pick_download_location")
    def run_test(self, pick_location):
        """Run the PrepareDownloadLocationTask class."""
        dnf_manager = Mock()

        with tempfile.TemporaryDirectory() as path:
            # Mock the download location.
            pick_location.return_value = path

            # Create files in the download location.
            os.mknod(os.path.join(path, "f1"))
            os.mknod(os.path.join(path, "f2"))
            os.mknod(os.path.join(path, "f3"))

            task = PrepareDownloadLocationTask(dnf_manager)
            self.assertEqual(task.run(), path)

            # The manager should apply the location.
            dnf_manager.set_download_location.assert_called_once_with(path)

            # The files should be deleted.
            self.assertFalse(os.path.exists(os.path.join(path, "f1")))
            self.assertFalse(os.path.exists(os.path.join(path, "f2")))
            self.assertFalse(os.path.exists(os.path.join(path, "f3")))


class CleanUpDownloadLocationTaskTestCase(unittest.TestCase):

    @patch("pyanaconda.modules.payloads.payload.dnf.installation.shutil")
    def run_nonexistent_test(self, shutil_mock):
        """Run the CleanUpDownloadLocationTask class for nonexistent location."""
        dnf_manager = DNFManager()
        dnf_manager.set_download_location("/my/nonexistent/path")

        task = CleanUpDownloadLocationTask(dnf_manager)
        task.run()

        shutil_mock.rmtree.assert_not_called()

    def run_test(self):
        """Run the CleanUpDownloadLocationTask class."""
        dnf_manager = DNFManager()

        with tempfile.TemporaryDirectory() as path:
            # Mock the download location.
            dnf_manager.set_download_location(path)

            # Create files in the download location.
            os.mknod(os.path.join(path, "f1"))
            os.mknod(os.path.join(path, "f2"))
            os.mknod(os.path.join(path, "f3"))

            task = CleanUpDownloadLocationTask(dnf_manager)
            task.run()

            # The files should be deleted.
            self.assertFalse(os.path.exists(os.path.join(path, "f1")))
            self.assertFalse(os.path.exists(os.path.join(path, "f2")))
            self.assertFalse(os.path.exists(os.path.join(path, "f3")))


class ResolvePackagesTaskTestCase(unittest.TestCase):

    @patch("pyanaconda.modules.payloads.payload.dnf.installation.collect_driver_disk_requirements")
    @patch("pyanaconda.modules.payloads.payload.dnf.installation.collect_platform_requirements")
    @patch("pyanaconda.modules.payloads.payload.dnf.installation.collect_language_requirements")
    @patch("pyanaconda.modules.payloads.payload.dnf.installation.collect_remote_requirements")
    @patch("pyanaconda.modules.payloads.payload.dnf.validation.get_kernel_package")
    def resolve_test(self, kernel_getter, req_getter1, req_getter2, req_getter3, req_getter4):
        """Test the successful ResolvePackagesTask task."""
        kernel_getter.return_value = None

        req_getter1.return_value = [
            Requirement.for_group("r1"),
            Requirement.for_group("r2")
        ]
        req_getter2.return_value = [
            Requirement.for_group("r3")
        ]
        req_getter3.return_value = [
            Requirement.for_package("r4"),
            Requirement.for_package("r5")
        ]
        req_getter4.return_value = [
            Requirement.for_package("r6")
        ]

        selection = PackagesSelectionData()
        selection.excluded_groups = ["r3"]
        selection.excluded_packages = ["r6"]

        dnf_manager = Mock()
        dnf_manager.default_environment = None

        task = ResolvePackagesTask(dnf_manager, selection)
        task.run()

        dnf_manager.clear_selection.assert_called_once_with()
        dnf_manager.disable_modules.assert_called_once_with([])
        dnf_manager.enable_modules.assert_called_once_with([])
        dnf_manager.apply_specs.assert_called_once_with(
            ["@core", "@r1", "@r2", "r4", "r5"], ["@r3", "r6"]
        )
        dnf_manager.resolve_selection.assert_called_once_with()

    @patch("pyanaconda.modules.payloads.payload.dnf.installation.collect_driver_disk_requirements")
    @patch("pyanaconda.modules.payloads.payload.dnf.installation.collect_platform_requirements")
    @patch("pyanaconda.modules.payloads.payload.dnf.installation.collect_language_requirements")
    @patch("pyanaconda.modules.payloads.payload.dnf.installation.collect_remote_requirements")
    @patch("pyanaconda.modules.payloads.payload.dnf.validation.get_kernel_package")
    def fail_test(self, kernel_getter, req_getter1, req_getter2, req_getter3, req_getter4):
        """Test the failed ResolvePackagesTask task."""
        kernel_getter.return_value = None
        req_getter1.return_value = []
        req_getter2.return_value = []
        req_getter3.return_value = []
        req_getter4.return_value = []

        selection = PackagesSelectionData()

        dnf_manager = Mock()
        dnf_manager.default_environment = None

        dnf_manager.disable_modules.side_effect = MissingSpecsError("e1")
        dnf_manager.apply_specs.side_effect = MissingSpecsError("e2")

        with self.assertRaises(NonCriticalInstallationError) as cm:
            task = ResolvePackagesTask(dnf_manager, selection)
            task.run()

        expected = "e1\n\ne2"
        self.assertEqual(str(cm.exception), expected)

        dnf_manager.enable_modules.side_effect = BrokenSpecsError("e3")
        dnf_manager.resolve_selection.side_effect = InvalidSelectionError("e4")

        with self.assertRaises(PayloadInstallationError) as cm:
            task = ResolvePackagesTask(dnf_manager, selection)
            task.run()

        expected = "e3\n\ne4"
        self.assertEqual(str(cm.exception), expected)
