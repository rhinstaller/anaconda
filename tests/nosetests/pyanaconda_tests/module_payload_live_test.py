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
import stat
import unittest

from unittest.mock import patch, call, Mock
from tempfile import TemporaryDirectory

from pyanaconda.core.constants import INSTALL_TREE
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.modules.common.errors.payload import InstallError
from pyanaconda.modules.payloads.base.initialization import UpdateBLSConfigurationTask
from pyanaconda.modules.payloads.base.installation import InstallFromImageTask
from pyanaconda.modules.payloads.base.utils import create_rescue_image, get_kernel_version_list


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

    def _prepare_rescue_test_dirs(self, temp_dir,
                                  fake_machine_id,
                                  fake_new_kernel_pkg,
                                  fake_postinst_scripts_list):
        etc_path = os.path.join(temp_dir, "etc")
        postinst_path = os.path.join(etc_path, "kernel/postinst.d")
        sbin_path = os.path.join(temp_dir, "usr/sbin")

        os.makedirs(etc_path)

        if fake_machine_id:
            open(os.path.join(etc_path, "machine-id"), "wt").close()

        if fake_new_kernel_pkg:
            os.makedirs(sbin_path)
            open(os.path.join(sbin_path, "new-kernel-pkg"), "wb").close()

        if fake_postinst_scripts_list:
            os.makedirs(postinst_path)
            for path in fake_postinst_scripts_list:
                path = os.path.join(postinst_path, path)
                open(path, "wt").close()
                os.chmod(path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

    def kernel_list_empty_test(self):
        """Test empty get kernel list function."""
        with TemporaryDirectory() as temp:
            result = get_kernel_version_list(temp)

        self.assertEqual(result, [])

    def kernel_list_test(self):
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

            self.assertListEqual(kernel_list, self._kernel_test_valid_list)

    @patch("pyanaconda.modules.payloads.base.utils.execWithRedirect")
    def create_rescue_image_with_new_kernel_pkg_test(self, exec_with_redirect):
        """Test creation of rescue image with kernel pkg."""
        kernel_version_list = ["kernel-v1.fc2000.x86_64", "kernel-sad-kernel"]
        with TemporaryDirectory() as temp:
            self._prepare_rescue_test_dirs(temp,
                                           fake_machine_id=True,
                                           fake_new_kernel_pkg=True,
                                           fake_postinst_scripts_list=[])

            create_rescue_image(temp, kernel_version_list)

            calls = [call("systemd-machine-id-setup", [], root=temp)]
            for kernel in kernel_version_list:
                calls.append(call("new-kernel-pkg", ["--rpmposttrans", kernel], root=temp))

            exec_with_redirect.assert_has_calls(calls)

    @patch("pyanaconda.modules.payloads.base.utils.execWithRedirect")
    def create_rescue_image_without_machine_id_test(self, exec_with_redirect):
        """Test creation of rescue image without machine-id file."""
        kernel_version_list = ["kernel-v1.fc2000.x86_64", "kernel-sad-kernel"]
        with TemporaryDirectory() as temp:
            self._prepare_rescue_test_dirs(temp,
                                           fake_machine_id=False,
                                           fake_new_kernel_pkg=True,
                                           fake_postinst_scripts_list=[])

            create_rescue_image(temp, kernel_version_list)

            calls = [call("systemd-machine-id-setup", [], root=temp)]
            for kernel in kernel_version_list:
                calls.append(call("new-kernel-pkg", ["--rpmposttrans", kernel], root=temp))

            exec_with_redirect.assert_has_calls(calls)

    @patch("pyanaconda.modules.payloads.base.utils.execWithRedirect")
    def create_rescue_image_with_postinst_scripts_test(self, exec_with_redirect):
        """Test creation of rescue image with postinst scripts."""
        kernel_version_list = ["kernel-v1.fc2000.x86_64", "kernel-sad-kernel"]
        postinst_scripts = ["01-create", "02-rule", "03-aaaand-we-lost"]
        with TemporaryDirectory() as temp:
            self._prepare_rescue_test_dirs(temp,
                                           fake_machine_id=True,
                                           fake_new_kernel_pkg=False,
                                           fake_postinst_scripts_list=postinst_scripts)

            with self.assertLogs(level="WARNING") as cm:
                create_rescue_image(temp, kernel_version_list)

                self.assertTrue(any(map(lambda x: "new-kernel-pkg does not exist" in x,
                                        cm.output)))

            calls = [call("systemd-machine-id-setup", [], root=temp)]
            for kernel in kernel_version_list:
                for script in sorted(postinst_scripts):
                    script = os.path.join("/etc/kernel/postinst.d", script)
                    kernel_path = "/boot/vmlinuz-{}".format(kernel)
                    calls.append(call(script, [kernel, kernel_path], root=temp))

            exec_with_redirect.assert_has_calls(calls)


class LiveTasksTestCase(unittest.TestCase):

    def _prepare_bls_test_env(self, temp_dir, fake_kernel_pkg, bls_entries):
        sbin_path = os.path.join(temp_dir, "usr/sbin")
        entries_path = os.path.join(temp_dir, "boot/loader/entries")
        lib_modules_path = os.path.join(temp_dir, "lib/modules")

        if fake_kernel_pkg:
            os.makedirs(sbin_path)
            open(os.path.join(sbin_path, "new-kernel-pkg"), "wb").close()
            return

        os.makedirs(entries_path)
        os.makedirs(lib_modules_path)

        if bls_entries:
            for entry in bls_entries:
                open(os.path.join(entries_path, entry), "wt").close()

    @patch("pyanaconda.modules.payloads.base.installation.create_rescue_image")
    @patch("pyanaconda.modules.payloads.base.installation.execWithRedirect")
    def install_image_task_test(self, exec_with_redirect, create_rescue_image_mock):
        """Test installation from an image task."""
        dest_path = "/destination/path"
        kernel_version_list = ["kernel-v1.fc2000.x86_64", "kernel-sad-kernel"]
        source = Mock()
        exec_with_redirect.return_value = 0

        InstallFromImageTask(dest_path, kernel_version_list, source).run()

        expected_rsync_args = ["-pogAXtlHrDx", "--exclude", "/dev/", "--exclude", "/proc/",
                               "--exclude", "/tmp/*", "--exclude", "/sys/", "--exclude", "/run/",
                               "--exclude", "/boot/*rescue*", "--exclude", "/boot/loader/",
                               "--exclude", "/boot/efi/loader/",
                               "--exclude", "/etc/machine-id", INSTALL_TREE + "/", dest_path]

        exec_with_redirect.assert_called_once_with("rsync", expected_rsync_args)
        create_rescue_image_mock.assert_called_once_with(dest_path, kernel_version_list)

    @patch("pyanaconda.modules.payloads.base.installation.create_rescue_image")
    @patch("pyanaconda.modules.payloads.base.installation.execWithRedirect")
    def install_image_task_source_unready_test(self, exec_with_redirect, create_rescue_image_mock):
        """Test installation from an image task when source is not ready."""
        dest_path = "/destination/path"
        kernel_version_list = ["kernel-v1.fc2000.x86_64", "kernel-sad-kernel"]
        source = Mock()
        exec_with_redirect.return_value = 0

        InstallFromImageTask(dest_path, kernel_version_list, source).run()

        expected_rsync_args = ["-pogAXtlHrDx", "--exclude", "/dev/", "--exclude", "/proc/",
                               "--exclude", "/tmp/*", "--exclude", "/sys/", "--exclude", "/run/",
                               "--exclude", "/boot/*rescue*", "--exclude", "/boot/loader/",
                               "--exclude", "/boot/efi/loader/",
                               "--exclude", "/etc/machine-id", INSTALL_TREE + "/", dest_path]

        exec_with_redirect.assert_called_once_with("rsync", expected_rsync_args)
        create_rescue_image_mock.assert_called_once_with(dest_path, kernel_version_list)

    @patch("pyanaconda.modules.payloads.base.installation.create_rescue_image")
    @patch("pyanaconda.modules.payloads.base.installation.execWithRedirect")
    def install_image_task_failed_exception_test(self, exec_with_redirect,
                                                 create_rescue_image_mock):
        """Test installation from an image task with exception."""
        dest_path = "/destination/path"
        kernel_version_list = ["kernel-v1.fc2000.x86_64", "kernel-sad-kernel"]
        source = Mock()
        exec_with_redirect.side_effect = OSError("mock exception")

        with self.assertLogs(level="ERROR") as cm:
            with self.assertRaises(InstallError):
                InstallFromImageTask(dest_path, kernel_version_list, source).run()

            self.assertTrue(any(map(lambda x: "mock exception" in x, cm.output)))

        expected_rsync_args = ["-pogAXtlHrDx", "--exclude", "/dev/", "--exclude", "/proc/",
                               "--exclude", "/tmp/*", "--exclude", "/sys/", "--exclude", "/run/",
                               "--exclude", "/boot/*rescue*", "--exclude", "/boot/loader/",
                               "--exclude", "/boot/efi/loader/",
                               "--exclude", "/etc/machine-id", INSTALL_TREE + "/", dest_path]

        exec_with_redirect.assert_called_once_with("rsync", expected_rsync_args)
        create_rescue_image_mock.assert_not_called()

    @patch("pyanaconda.modules.payloads.base.installation.create_rescue_image")
    @patch("pyanaconda.modules.payloads.base.installation.execWithRedirect")
    def install_image_task_failed_return_code_test(self, exec_with_redirect,
                                                   create_rescue_image_mock):
        """Test installation from an image task with bad return code."""
        dest_path = "/destination/path"
        kernel_version_list = ["kernel-v1.fc2000.x86_64", "kernel-sad-kernel"]
        source = Mock()
        exec_with_redirect.return_value = 11

        with self.assertLogs(level="INFO") as cm:
            with self.assertRaises(InstallError):
                InstallFromImageTask(dest_path, kernel_version_list, source).run()

            self.assertTrue(any(map(lambda x: "exited with code 11" in x, cm.output)))

        expected_rsync_args = ["-pogAXtlHrDx", "--exclude", "/dev/", "--exclude", "/proc/",
                               "--exclude", "/tmp/*", "--exclude", "/sys/", "--exclude", "/run/",
                               "--exclude", "/boot/*rescue*", "--exclude", "/boot/loader/",
                               "--exclude", "/boot/efi/loader/",
                               "--exclude", "/etc/machine-id", INSTALL_TREE + "/", dest_path]

        exec_with_redirect.assert_called_once_with("rsync", expected_rsync_args)
        create_rescue_image_mock.assert_not_called()

    @patch("pyanaconda.modules.payloads.base.initialization.execWithRedirect")
    def update_bls_configuration_task_no_bls_system_test(self, exec_with_redirect):
        """Test update bls configuration task on no BLS system."""
        kernel_version_list = ["kernel-v1.fc2000.x86_64", "kernel-sad-kernel"]

        with TemporaryDirectory() as temp:
            self._prepare_bls_test_env(temp, fake_kernel_pkg=True, bls_entries=[])

            UpdateBLSConfigurationTask(temp, kernel_version_list).run()

            # nothing should be done when new-kernel-pkg is present
            exec_with_redirect.assert_not_called()

    @patch("pyanaconda.modules.payloads.base.initialization.execWithRedirect")
    def update_bls_configuration_task_old_entries_test(self, exec_with_redirect):
        """Test update bls configuration task with old bls entries."""
        kernel_version_list = ["kernel-v1.fc2000.x86_64", "kernel-sad-kernel"]
        bls_entries = ["one.conf", "two.conf", "three_trillions_twenty_two.noconf"]

        with TemporaryDirectory() as temp:
            self._prepare_bls_test_env(temp, fake_kernel_pkg=False, bls_entries=bls_entries)

            UpdateBLSConfigurationTask(temp, kernel_version_list).run()

            entries_path = os.path.join(temp, "boot/loader/entries")
            for entry in bls_entries:
                entry = os.path.join(entries_path, entry)
                if entry[-7:] != ".noconf":
                    self.assertFalse(os.path.exists(entry),
                                     msg="File {} should be removed".format(entry))
                else:
                    self.assertTrue(os.path.exists(entry),
                                    msg="File {} shouldn't be removed".format(entry))

            calls = []
            for kernel in kernel_version_list:
                calls.append(
                    call("kernel-install",
                         ["add", kernel, "/lib/modules/{0}/vmlinuz".format(kernel)],
                         root=temp),
                )

            exec_with_redirect.assert_has_calls(calls)

    @patch("pyanaconda.modules.payloads.base.initialization.execWithRedirect")
    def update_bls_configuration_task_no_old_entries_test(self, exec_with_redirect):
        """Test update bls configuration task without old bls entries."""
        kernel_version_list = ["kernel-v1.fc2000.x86_64", "kernel-sad-kernel"]
        bls_entries = ["three_trillions_twenty_two.noconf"]

        with TemporaryDirectory() as temp:
            self._prepare_bls_test_env(temp, fake_kernel_pkg=False, bls_entries=bls_entries)

            UpdateBLSConfigurationTask(temp, kernel_version_list).run()

            entries_path = os.path.join(temp, "boot/loader/entries")
            entry = os.path.join(entries_path, bls_entries[0])
            self.assertTrue(os.path.exists(entry),
                            msg="File {} shouldn't be removed".format(entry))

            calls = []
            for kernel in kernel_version_list:
                calls.append(
                    call("kernel-install",
                         ["add", kernel, "/lib/modules/{0}/vmlinuz".format(kernel)],
                         root=temp),
                )

            exec_with_redirect.assert_has_calls(calls)
