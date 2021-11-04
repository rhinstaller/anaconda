#
# Copyright (C) 2019  Red Hat, Inc.
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
# Red Hat Author(s): Jiri Konecny <jkonecny@redhat.com>
#
import os
import tempfile
import unittest
import pytest

from unittest.mock import patch

from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.util import join_paths
from pyanaconda.modules.common.errors.installation import PayloadInstallationError
from pyanaconda.modules.payloads.payload.live_image.installation import VerifyImageChecksum, \
    InstallFromImageTask, InstallFromTarTask
from pyanaconda.modules.payloads.payload.live_os.utils import get_kernel_version_list


class LiveUtilsTestCase(unittest.TestCase):

    def setUp(self):
        self._kernel_test_files_list = []
        self._kernel_test_valid_list = []

    def _create_kernel_files(self, kernel_file, is_valid):
        kernel_dir = os.path.dirname(kernel_file)
        name = os.path.basename(kernel_file)

        os.makedirs(kernel_dir, exist_ok=True)
        open(kernel_file, 'wb').close()

        self._kernel_test_files_list.append(name[8:])
        if is_valid:
            self._kernel_test_valid_list.append(name[8:])

    def test_kernel_list_empty(self):
        """Test empty get kernel list function."""
        with tempfile.TemporaryDirectory() as temp:
            result = get_kernel_version_list(temp)

        assert result == []

    def test_kernel_list(self):
        """Test get kernel list function."""
        with tempfile.TemporaryDirectory() as temp:

            boot_base = os.path.join(temp, "boot/vmlinuz-{}")
            efi_base = os.path.join(temp, "boot/efi/EFI/", conf.bootloader.efi_dir, "vmlinuz-{}")

            self._create_kernel_files(boot_base.format("boot-test1"), is_valid=True)
            self._create_kernel_files(boot_base.format("boot-test2.x86_64"), is_valid=True)
            self._create_kernel_files(boot_base.format("rescue-kernel.ppc64"), is_valid=False)
            self._create_kernel_files(efi_base.format("efi-test1"), is_valid=True)
            self._create_kernel_files(efi_base.format("efi-test2"), is_valid=True)
            self._create_kernel_files(efi_base.format("efi-test3.fc2000.i386"), is_valid=True)
            self._create_kernel_files(efi_base.format("efi-test-rescue-kernel"), is_valid=False)

            kernel_list = get_kernel_version_list(temp)

            assert kernel_list == self._kernel_test_valid_list


class InstallFromImageTaskTestCase(unittest.TestCase):
    """Test the InstallFromImageTask class."""

    @patch("pyanaconda.modules.payloads.payload.live_image.installation.os.sync")
    @patch("pyanaconda.modules.payloads.payload.live_image.installation.execWithRedirect")
    def test_install_image_task(self, exec_with_redirect, os_sync):
        """Test installation from an image task."""
        exec_with_redirect.return_value = 0

        with tempfile.TemporaryDirectory() as mount_point:
            task = InstallFromImageTask(
                sysroot="/mnt/root",
                mount_point=mount_point
            )
            task.run()

        exec_with_redirect.assert_called_once_with("rsync", [
            "-pogAXtlHrDx",
            "--stats",
            "--exclude", "/dev/",
            "--exclude", "/proc/",
            "--exclude", "/tmp/*",
            "--exclude", "/sys/",
            "--exclude", "/run/",
            "--exclude", "/boot/*rescue*",
            "--exclude", "/boot/loader/",
            "--exclude", "/boot/efi/loader/",
            "--exclude", "/etc/machine-id",
            mount_point + "/",
            "/mnt/root"
        ])

    @patch("pyanaconda.modules.payloads.payload.live_image.installation.os.sync")
    @patch("pyanaconda.modules.payloads.payload.live_image.installation.execWithRedirect")
    def test_install_image_task_failed_exception(self, exec_with_redirect, os_sync):
        """Test installation from an image task with exception."""
        exec_with_redirect.side_effect = OSError("Fake!")

        with tempfile.TemporaryDirectory() as mount_point:
            task = InstallFromImageTask(
                sysroot="/mnt/root",
                mount_point=mount_point
            )

            with pytest.raises(PayloadInstallationError) as cm:
                task.run()

        msg = "Failed to install image: Fake!"
        assert str(cm.value) == msg

    @patch("pyanaconda.modules.payloads.payload.live_image.installation.os.sync")
    @patch("pyanaconda.modules.payloads.payload.live_image.installation.execWithRedirect")
    def test_install_image_task_failed_return_code(self, exec_with_redirect, os_sync):
        """Test installation from an image task with bad return code."""
        exec_with_redirect.return_value = 11

        with tempfile.TemporaryDirectory() as mount_point:
            task = InstallFromImageTask(
                sysroot="/mnt/root",
                mount_point=mount_point
            )

            with pytest.raises(PayloadInstallationError) as cm:
                task.run()

        msg = "Failed to install image: rsync exited with code 11"
        assert str(cm.value) == msg


class InstallFromTarTaskTestCase(unittest.TestCase):
    """Test the InstallFromTarTask class."""

    @patch("pyanaconda.modules.payloads.payload.live_image.installation.os.sync")
    @patch("pyanaconda.modules.payloads.payload.live_image.installation.execWithRedirect")
    def test_install_tar_task(self, exec_with_redirect, os_sync):
        """Test installation from a tarball."""
        exec_with_redirect.return_value = 0

        with tempfile.NamedTemporaryFile("w") as f:
            task = InstallFromTarTask(
                sysroot="/mnt/root",
                tarfile=f.name
            )
            task.run()

        exec_with_redirect.assert_called_once_with("tar", [
            "--numeric-owner",
            "--selinux",
            "--acls",
            "--xattrs",
            "--xattrs-include", "*",
            "--exclude", "./dev/*",
            "--exclude", "./proc/*",
            "--exclude", "./tmp/*",
            "--exclude", "./sys/*",
            "--exclude", "./run/*",
            "--exclude", "./boot/*rescue*",
            "--exclude", "./boot/loader",
            "--exclude", "./boot/efi/loader",
            "--exclude", "./etc/machine-id",
            "-xaf", f.name,
            "-C", "/mnt/root"
        ])

    @patch("pyanaconda.modules.payloads.payload.live_image.installation.os.sync")
    @patch("pyanaconda.modules.payloads.payload.live_image.installation.execWithRedirect")
    def test_install_tar_task_failed_exception(self, exec_with_redirect, os_sync):
        """Test installation from a tarball with an exception."""
        exec_with_redirect.side_effect = OSError("Fake!")

        with tempfile.NamedTemporaryFile("w") as f:
            task = InstallFromTarTask(
                sysroot="/mnt/root",
                tarfile=f.name
            )

            with pytest.raises(PayloadInstallationError) as cm:
                task.run()

        msg = "Failed to install tar: Fake!"
        assert str(cm.value) == msg


class VerifyImageChecksumTestCase(unittest.TestCase):
    """Test the VerifyImageChecksum class."""

    def _create_image(self, f):
        """Create a fake image."""
        f.write("IMAGE CONTENT")
        f.flush()

    def test_verify_no_checksum(self):
        """Test the verification of a checksum."""
        with tempfile.TemporaryDirectory() as d:
            f_name = join_paths(d, "image")

            task = VerifyImageChecksum(
                image_path=f_name,
                checksum=""
            )

            with self.assertLogs(level="DEBUG") as cm:
                task.run()

        msg = "No checksum to verify."
        assert msg in "\n".join(cm.output)

    def test_verify_checksum(self):
        """Test the verification of a checksum."""
        checksum = \
            "7190E29480A9081FD917E33990F00098" \
            "DD9FBD348BC52B0775780348BDA3A617"

        with tempfile.NamedTemporaryFile("w") as f:
            self._create_image(f)

            task = VerifyImageChecksum(
                image_path=f.name,
                checksum=checksum
            )

            with self.assertLogs(level="DEBUG") as cm:
                task.run()

        msg = "Checksum of the image does match."
        assert msg in "\n".join(cm.output)

    def test_verify_wrong_checksum(self):
        """Test the verification of a wrong checksum."""
        with tempfile.NamedTemporaryFile("w") as f:
            self._create_image(f)

            task = VerifyImageChecksum(
                image_path=f.name,
                checksum="incorrect"
            )

            with pytest.raises(PayloadInstallationError) as cm:
                task.run()

        msg = "Checksum of the image does not match."
        assert str(cm.value) == msg
