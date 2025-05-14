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
import unittest
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

import pytest

from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import INSTALL_TREE
from pyanaconda.modules.common.errors.payload import InstallError
from pyanaconda.modules.payloads.base.installation import InstallFromImageTask
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
        with TemporaryDirectory() as temp:
            result = get_kernel_version_list(temp)

        assert result == []

    def test_kernel_list(self):
        """Test get kernel list function."""
        with TemporaryDirectory() as temp:

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


class LiveTasksTestCase(unittest.TestCase):

    @patch("pyanaconda.modules.payloads.base.installation.execWithRedirect")
    def test_install_image_task(self, exec_with_redirect, ):
        """Test installation from an image task."""
        dest_path = "/destination/path"
        source = Mock()
        exec_with_redirect.return_value = 0

        InstallFromImageTask(dest_path, source).run()

        expected_rsync_args = ["-pogAXtlHrDx", "--exclude", "/dev/", "--exclude", "/proc/",
                               "--exclude", "/tmp/*", "--exclude", "/sys/", "--exclude", "/run/",
                               "--exclude", "/boot/*rescue*", "--exclude", "/boot/loader/",
                               "--exclude", "/boot/efi/loader/",
                               "--exclude", "/etc/machine-id", "--exclude", "/etc/machine-info",
                               INSTALL_TREE + "/", dest_path]

        exec_with_redirect.assert_called_once_with("rsync", expected_rsync_args)

    @patch("pyanaconda.modules.payloads.base.installation.execWithRedirect")
    def test_install_image_task_source_unready(self, exec_with_redirect):
        """Test installation from an image task when source is not ready."""
        dest_path = "/destination/path"
        source = Mock()
        exec_with_redirect.return_value = 0

        InstallFromImageTask(dest_path, source).run()

        expected_rsync_args = ["-pogAXtlHrDx", "--exclude", "/dev/", "--exclude", "/proc/",
                               "--exclude", "/tmp/*", "--exclude", "/sys/", "--exclude", "/run/",
                               "--exclude", "/boot/*rescue*", "--exclude", "/boot/loader/",
                               "--exclude", "/boot/efi/loader/",
                               "--exclude", "/etc/machine-id", "--exclude", "/etc/machine-info",
                               INSTALL_TREE + "/", dest_path]

        exec_with_redirect.assert_called_once_with("rsync", expected_rsync_args)

    @patch("pyanaconda.modules.payloads.base.installation.execWithRedirect")
    def test_install_image_task_failed_exception(self, exec_with_redirect):
        """Test installation from an image task with exception."""
        dest_path = "/destination/path"
        source = Mock()
        exec_with_redirect.side_effect = OSError("mock exception")

        with self.assertLogs(level="ERROR") as cm:
            with pytest.raises(InstallError):
                InstallFromImageTask(dest_path, source).run()

            assert any(map(lambda x: "mock exception" in x, cm.output))

        expected_rsync_args = ["-pogAXtlHrDx", "--exclude", "/dev/", "--exclude", "/proc/",
                               "--exclude", "/tmp/*", "--exclude", "/sys/", "--exclude", "/run/",
                               "--exclude", "/boot/*rescue*", "--exclude", "/boot/loader/",
                               "--exclude", "/boot/efi/loader/",
                               "--exclude", "/etc/machine-id", "--exclude", "/etc/machine-info",
                               INSTALL_TREE + "/", dest_path]

        exec_with_redirect.assert_called_once_with("rsync", expected_rsync_args)

    @patch("pyanaconda.modules.payloads.base.installation.execWithRedirect")
    def test_install_image_task_failed_return_code(self, exec_with_redirect):
        """Test installation from an image task with bad return code."""
        dest_path = "/destination/path"
        source = Mock()
        exec_with_redirect.return_value = 11

        with self.assertLogs(level="INFO") as cm:
            with pytest.raises(InstallError):
                InstallFromImageTask(dest_path, source).run()

            assert any(map(lambda x: "exited with code 11" in x, cm.output)) is True

        expected_rsync_args = ["-pogAXtlHrDx", "--exclude", "/dev/", "--exclude", "/proc/",
                               "--exclude", "/tmp/*", "--exclude", "/sys/", "--exclude", "/run/",
                               "--exclude", "/boot/*rescue*", "--exclude", "/boot/loader/",
                               "--exclude", "/boot/efi/loader/",
                               "--exclude", "/etc/machine-id", "--exclude", "/etc/machine-info",
                               INSTALL_TREE + "/", dest_path]

        exec_with_redirect.assert_called_once_with("rsync", expected_rsync_args)
