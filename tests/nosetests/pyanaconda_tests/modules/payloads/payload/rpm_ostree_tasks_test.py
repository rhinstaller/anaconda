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
import os

import unittest
from unittest.mock import patch, call, MagicMock

from pyanaconda.core.glib import Variant, GError
from pyanaconda.modules.common.structures.rpm_ostree import RPMOSTreeConfigurationData
from pyanaconda.payload.errors import PayloadInstallError

from pyanaconda.modules.payloads.payload.rpm_ostree.installation import \
    PrepareOSTreeMountTargetsTask, CopyBootloaderDataTask, InitOSTreeFsAndRepoTask, \
    ChangeOSTreeRemoteTask, ConfigureBootloader, DeployOSTreeTask, PullRemoteAndDeleteTask, \
    SetSystemRootTask


def _make_config_data():
    """Create OSTree configuration data for testing

    :return RPMOSTreeConfigurationData: a data instance with all fields filled
    """
    data = RPMOSTreeConfigurationData()
    data.url = "url"
    data.osname = "osname"
    data.gpg_verification_enabled = True
    data.ref = "ref"
    data.remote = "remote"
    return data


class PrepareOSTreeMountTargetsTaskTestCase(unittest.TestCase):

    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.safe_exec_with_redirect")
    def setup_internal_bindmount_test(self, exec_mock):
        """Test OSTree mount target prepare task _setup_internal_bindmount()"""
        data = _make_config_data()
        task = PrepareOSTreeMountTargetsTask("/sysroot", "/physroot", data)
        self.assertEqual(len(task._internal_mounts), 0)

        # everything left out
        task._setup_internal_bindmount("/src")
        exec_mock.assert_called_once_with("mount", ["--rbind", "/physroot/src", "/sysroot/src"])
        self.assertListEqual(task._internal_mounts, ["/sysroot/src"])
        task._internal_mounts.clear()
        exec_mock.reset_mock()

        # all equal to defaults but present - same as above but dest is used
        task._setup_internal_bindmount("/src", "/dest", True, False, True)
        exec_mock.assert_called_once_with("mount", ["--rbind", "/physroot/src", "/sysroot/dest"])
        self.assertListEqual(task._internal_mounts, ["/sysroot/dest"])
        task._internal_mounts.clear()
        exec_mock.reset_mock()

        # src_physical off - makes it sysroot->sysroot
        task._setup_internal_bindmount("/src", "/dest", False, False, True)
        exec_mock.assert_called_once_with("mount", ["--rbind", "/sysroot/src", "/sysroot/dest"])
        self.assertListEqual(task._internal_mounts, ["/sysroot/dest"])
        task._internal_mounts.clear()
        exec_mock.reset_mock()

        # bind_ro requires two calls
        task._setup_internal_bindmount("/src", "/dest", True, True, True)
        exec_mock.assert_has_calls([
            call("mount", ["--bind", "/physroot/src", "/physroot/src"]),
            call("mount", ["--bind", "-o", "remount,ro", "/physroot/src", "/physroot/src"])
        ])
        self.assertEqual(len(exec_mock.mock_calls), 2)
        self.assertListEqual(task._internal_mounts, ["/physroot/src"])
        task._internal_mounts.clear()
        exec_mock.reset_mock()

        # recurse off - bind instead of rbind
        task._setup_internal_bindmount("/src", "/dest", True, False, False)
        exec_mock.assert_called_once_with("mount", ["--bind", "/physroot/src", "/sysroot/dest"])
        self.assertListEqual(task._internal_mounts, ["/sysroot/dest"])
        task._internal_mounts.clear()
        exec_mock.reset_mock()

    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.safe_exec_with_redirect")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.mkdirChain")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.STORAGE")
    def run_with_var_test(self, storage_mock, mkdir_mock, exec_mock):
        """Test OSTree mount target prepare task run() with /var"""
        data = _make_config_data()
        devicetree_mock = storage_mock.get_proxy()

        devicetree_mock.GetMountPoints.return_value = {
            "/": "somewhere", "/etc": "elsewhere", "/home": "here", "/var": "whatever"
        }

        task = PrepareOSTreeMountTargetsTask("/sysroot", "/physroot", data)
        created_mount_points = task.run()

        self.assertListEqual(
            created_mount_points,
            ["/sysroot/usr", "/sysroot/dev", "/sysroot/proc", "/sysroot/run", "/sysroot/sys",
             "/sysroot/var", "/sysroot/etc", "/sysroot/home", "/sysroot/sysroot"]
        )
        exec_mock.assert_has_calls([
            call("mount", ["--bind", "/sysroot/usr", "/sysroot/usr"]),
            call("mount", ["--bind", "-o", "remount,ro", "/sysroot/usr", "/sysroot/usr"]),
            call("mount", ["--rbind", "/physroot/dev", "/sysroot/dev"]),
            call("mount", ["--rbind", "/physroot/proc", "/sysroot/proc"]),
            call("mount", ["--rbind", "/physroot/run", "/sysroot/run"]),
            call("mount", ["--rbind", "/physroot/sys", "/sysroot/sys"]),
            call("mount", ["--bind", "/physroot/var", "/sysroot/var"]),
            call("systemd-tmpfiles",
                 ["--create", "--boot", "--root=/sysroot", "--prefix=/var/home"]),
            call("systemd-tmpfiles",
                 ["--create", "--boot", "--root=/sysroot", "--prefix=/var/roothome"]),
            call("systemd-tmpfiles",
                 ["--create", "--boot", "--root=/sysroot", "--prefix=/var/lib/rpm"]),
            call("systemd-tmpfiles",
                 ["--create", "--boot", "--root=/sysroot", "--prefix=/var/opt"]),
            call("systemd-tmpfiles",
                 ["--create", "--boot", "--root=/sysroot", "--prefix=/var/srv"]),
            call("systemd-tmpfiles",
                 ["--create", "--boot", "--root=/sysroot", "--prefix=/var/usrlocal"]),
            call("systemd-tmpfiles",
                 ["--create", "--boot", "--root=/sysroot", "--prefix=/var/mnt"]),
            call("systemd-tmpfiles",
                 ["--create", "--boot", "--root=/sysroot", "--prefix=/var/media"]),
            call("systemd-tmpfiles",
                 ["--create", "--boot", "--root=/sysroot", "--prefix=/var/spool"]),
            call("systemd-tmpfiles",
                 ["--create", "--boot", "--root=/sysroot", "--prefix=/var/spool/mail"]),
            call("mount", ["--bind", "/physroot/etc", "/sysroot/etc"]),
            call("mount", ["--bind", "/physroot/home", "/sysroot/home"]),
            call("mount", ["--bind", "/physroot/", "/sysroot/sysroot"])
        ])
        self.assertEqual(len(exec_mock.mock_calls), 20)
        mkdir_mock.assert_called_once_with("/sysroot/var/lib")

    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.safe_exec_with_redirect")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.mkdirChain")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.STORAGE")
    def run_without_var_test(self, storage_mock, mkdir_mock, exec_mock):
        """Test OSTree mount target prepare task run() without /var"""
        data = _make_config_data()
        devicetree_mock = storage_mock.get_proxy()

        devicetree_mock.GetMountPoints.return_value = {
            "/": "somewhere", "/etc": "elsewhere", "/home": "here"
        }
        task = PrepareOSTreeMountTargetsTask("/sysroot", "/physroot", data)
        created_mount_points = task.run()

        self.assertListEqual(
            created_mount_points,
            ["/sysroot/usr", "/sysroot/dev", "/sysroot/proc", "/sysroot/run", "/sysroot/sys",
             "/sysroot/var", "/sysroot/etc", "/sysroot/home", "/sysroot/sysroot"]
        )
        exec_mock.assert_has_calls([
            call("mount", ["--bind", "/sysroot/usr", "/sysroot/usr"]),
            call("mount", ["--bind", "-o", "remount,ro", "/sysroot/usr", "/sysroot/usr"]),
            call("mount", ["--rbind", "/physroot/dev", "/sysroot/dev"]),
            call("mount", ["--rbind", "/physroot/proc", "/sysroot/proc"]),
            call("mount", ["--rbind", "/physroot/run", "/sysroot/run"]),
            call("mount", ["--rbind", "/physroot/sys", "/sysroot/sys"]),
            call("mount", ["--bind", "/physroot/ostree/deploy/osname/var", "/sysroot/var"]),
            call("systemd-tmpfiles",
                 ["--create", "--boot", "--root=/sysroot", "--prefix=/var/home"]),
            call("systemd-tmpfiles",
                 ["--create", "--boot", "--root=/sysroot", "--prefix=/var/roothome"]),
            call("systemd-tmpfiles",
                 ["--create", "--boot", "--root=/sysroot", "--prefix=/var/lib/rpm"]),
            call("systemd-tmpfiles",
                 ["--create", "--boot", "--root=/sysroot", "--prefix=/var/opt"]),
            call("systemd-tmpfiles",
                 ["--create", "--boot", "--root=/sysroot", "--prefix=/var/srv"]),
            call("systemd-tmpfiles",
                 ["--create", "--boot", "--root=/sysroot", "--prefix=/var/usrlocal"]),
            call("systemd-tmpfiles",
                 ["--create", "--boot", "--root=/sysroot", "--prefix=/var/mnt"]),
            call("systemd-tmpfiles",
                 ["--create", "--boot", "--root=/sysroot", "--prefix=/var/media"]),
            call("systemd-tmpfiles",
                 ["--create", "--boot", "--root=/sysroot", "--prefix=/var/spool"]),
            call("systemd-tmpfiles",
                 ["--create", "--boot", "--root=/sysroot", "--prefix=/var/spool/mail"]),
            call("mount", ["--bind", "/physroot/etc", "/sysroot/etc"]),
            call("mount", ["--bind", "/physroot/home", "/sysroot/home"]),
            call("mount", ["--bind", "/physroot/", "/sysroot/sysroot"])
        ])
        self.assertEqual(len(exec_mock.mock_calls), 20)
        mkdir_mock.assert_called_once_with("/sysroot/var/lib")


class CopyBootloaderDataTaskTestCase(unittest.TestCase):
    # variables to consider: efi, boot source + files & dirs therein

    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.STORAGE")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.os.path.isdir")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.os.listdir")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.safe_exec_with_redirect")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.os.path.islink")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.os.unlink")
    def run_noefi_noefidir_nolink_test(
            self, unlink_mock, islink_mock, exec_mock, listdir_mock, isdir_mock, storage_mock):
        """Test OSTree bootloader copy task run() with no EFI, no efi dir, and no links"""
        bootloader_mock = storage_mock.get_proxy()
        bootloader_mock.IsEFI.return_value = False

        isdir_mock.side_effect = [True, False, True]  # boot source, 2x listdir
        listdir_mock.return_value = ["some_file", "directory"]
        islink_mock.return_value = False

        task = CopyBootloaderDataTask("/sysroot", "/physroot")
        task.run()

        exec_mock.assert_called_once_with(
            "cp", ["-r", "-p", "/sysroot/usr/lib/ostree-boot/directory", "/physroot/boot"]
        )
        unlink_mock.assert_not_called()

    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.STORAGE")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.os.path.isdir")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.os.listdir")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.safe_exec_with_redirect")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.os.path.islink")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.os.unlink")
    def run_noefi_efidir_link_test(
            self, unlink_mock, islink_mock, exec_mock, listdir_mock, isdir_mock, storage_mock):
        """Test OSTree bootloader copy task run() with no EFI but efi dir and link"""
        bootloader_mock = storage_mock.get_proxy()
        bootloader_mock.IsEFI.return_value = False

        isdir_mock.side_effect = [True, False, True, True, True]  # boot source, 3x listdir, efi
        listdir_mock.return_value = ["some_file", "directory", "efi"]
        islink_mock.return_value = True

        task = CopyBootloaderDataTask("/sysroot", "/physroot")
        task.run()

        exec_mock.assert_called_once_with(
            "cp", ["-r", "-p", "/sysroot/usr/lib/ostree-boot/directory", "/physroot/boot"]
        )
        unlink_mock.assert_called_with("/physroot/boot/grub2/grubenv")

    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.STORAGE")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.os.path.isdir")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.os.listdir")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.safe_exec_with_redirect")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.os.path.islink")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.os.unlink")
    def run_efi_nolink_test(
            self, unlink_mock, islink_mock, exec_mock, listdir_mock, isdir_mock, storage_mock):
        """Test OSTree bootloader copy task run() with EFI, efi dir, and no links"""
        bootloader_mock = storage_mock.get_proxy()
        bootloader_mock.IsEFI.return_value = True

        isdir_mock.side_effect = [True, False, True, True, True]  # boot source, 3x listdir, efi
        listdir_mock.return_value = ["some_file", "directory", "efi"]
        islink_mock.return_value = False

        task = CopyBootloaderDataTask("/sysroot", "/physroot")
        task.run()

        exec_mock.assert_has_calls([
            call("cp", ["-r", "-p", "/sysroot/usr/lib/ostree-boot/directory", "/physroot/boot"]),
            call("cp", ["-r", "-p", "/sysroot/usr/lib/ostree-boot/efi", "/physroot/boot"])
        ])
        unlink_mock.assert_not_called()

    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.STORAGE")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.os.path.isdir")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.os.listdir")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.safe_exec_with_redirect")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.os.path.islink")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.os.unlink")
    def run_noefi_notadir_test(
            self, unlink_mock, islink_mock, exec_mock, listdir_mock, isdir_mock, storage_mock):
        """Test OSTree bootloader copy task run() with non-directory source of data"""
        bootloader_mock = storage_mock.get_proxy()
        bootloader_mock.IsEFI.return_value = False

        isdir_mock.side_effect = [False, False, True]  # boot source, 2x listdir
        listdir_mock.return_value = ["some_file", "directory"]
        islink_mock.return_value = False

        task = CopyBootloaderDataTask("/sysroot", "/physroot")
        task.run()

        exec_mock.assert_called_once_with(
            "cp", ["-r", "-p", "/sysroot/boot/directory", "/physroot/boot"]
        )
        unlink_mock.assert_not_called()


class InitOSTreeFsAndRepoTaskTestCase(unittest.TestCase):
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.safe_exec_with_redirect")
    def run_test(self, exec_mock):
        """Test OSTree fs and repo init task"""
        task = InitOSTreeFsAndRepoTask("/physroot")
        task.run()
        exec_mock.assert_called_once_with(
            "ostree",
            ["admin", "--sysroot=/physroot", "init-fs", "/physroot"]
        )


class ChangeOSTreeRemoteTaskTestCase(unittest.TestCase):
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.OSTree.Sysroot")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.conf")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.Gio.File")
    def _execute_run_once(self, use_sysroot, gpg_verify, verify_ssl,
                          gio_file_mock, conf_mock, sysroot_mock):
        new_mock = sysroot_mock.new()
        repo_mock = MagicMock()
        new_mock.get_repo.return_value = [None, repo_mock]
        conf_mock.payload.verify_ssl = verify_ssl
        path_mock = gio_file_mock.new_for_path()

        data = RPMOSTreeConfigurationData()
        data.url = "url"
        data.osname = "osname"
        data.gpg_verification_enabled = gpg_verify
        data.ref = "ref"
        data.remote = "remote"

        task = ChangeOSTreeRemoteTask(data, use_sysroot, "/physroot")
        task.run()

        repo_mock.remote_change.assert_called_once()
        the_call = repo_mock.remote_change.mock_calls[0]
        name, args, kwargs = the_call
        print(the_call, name, args, kwargs)
        self.assertEqual(len(args), 6)

        if use_sysroot:
            self.assertEqual(args[0], path_mock)
        else:
            self.assertEqual(args[0], None)
        self.assertEqual(args[2], "remote")
        self.assertEqual(args[3], "url")

        expected = {}
        if not gpg_verify:
            expected["gpg-verify"] = False
        if not verify_ssl:
            expected["tls-permissive"] = True
        var = args[4]
        self.assertEqual(type(var), Variant)
        self.assertDictEqual(var.unpack(), expected)

    def run_test(self):
        """Test OSTree remote change task"""
        # pylint: disable=no-value-for-parameter
        # check all combinations of all inputs
        for use_sysroot in (True, False):
            for verify_ssl in (True, False):
                for gpg_verify in (True, False):
                    self._execute_run_once(use_sysroot, gpg_verify, verify_ssl)


class ConfigureBootloaderTaskTestCase(unittest.TestCase):
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.safe_exec_with_redirect")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.os.rename")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.os.symlink")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.STORAGE")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.DeviceData")
    def btrfs_run_test(self, devdata_mock, storage_mock, symlink_mock, rename_mock, exec_mock):
        """Test OSTree bootloader config task, no BTRFS"""
        proxy_mock = storage_mock.get_proxy()
        proxy_mock.GetArguments.return_value = ["BOOTLOADER-ARGS"]
        proxy_mock.GetFstabSpec.return_value = "FSTAB-SPEC"
        proxy_mock.GetRootDevice.return_value = "device-name"
        devdata_mock.from_structure.return_value.type = "btrfs subvolume"

        with tempfile.TemporaryDirectory() as sysroot:
            os.makedirs(sysroot + "/boot/grub2")
            os.mknod(sysroot + "/boot/grub2/grub.cfg")

            task = ConfigureBootloader(sysroot, is_dirinstall=False)
            task.run()

            rename_mock.assert_called_once_with(
                sysroot + "/boot/grub2/grub.cfg",
                sysroot + "/boot/loader/grub.cfg"
            )
            symlink_mock.assert_called_once_with(
                "../loader/grub.cfg",
                sysroot + "/boot/grub2/grub.cfg"
            )
            exec_mock.assert_called_once_with(
                "ostree",
                ["admin", "instutil", "set-kargs", "BOOTLOADER-ARGS", "root=FSTAB-SPEC",
                 "rootflags=subvol=device-name"],
                root=sysroot
            )

    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.safe_exec_with_redirect")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.os.rename")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.os.symlink")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.STORAGE")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.DeviceData")
    def nonbtrfs_run_test(self, devdata_mock, storage_mock, symlink_mock, rename_mock, exec_mock):
        """Test OSTree bootloader config task, no BTRFS"""
        proxy_mock = storage_mock.get_proxy()
        proxy_mock.GetArguments.return_value = ["BOOTLOADER-ARGS"]
        proxy_mock.GetFstabSpec.return_value = "FSTAB-SPEC"
        proxy_mock.GetRootDevice.return_value = "device-name"
        devdata_mock.from_structure.return_value.type = "something-non-btrfs-subvolume-ish"

        with tempfile.TemporaryDirectory() as sysroot:
            os.makedirs(sysroot + "/boot/grub2")
            os.mknod(sysroot + "/boot/grub2/grub.cfg")

            task = ConfigureBootloader(sysroot, is_dirinstall=False)
            task.run()

            rename_mock.assert_called_once_with(
                sysroot + "/boot/grub2/grub.cfg",
                sysroot + "/boot/loader/grub.cfg"
            )
            symlink_mock.assert_called_once_with(
                "../loader/grub.cfg",
                sysroot + "/boot/grub2/grub.cfg"
            )
            exec_mock.assert_called_once_with(
                "ostree",
                ["admin", "instutil", "set-kargs", "BOOTLOADER-ARGS", "root=FSTAB-SPEC"],
                root=sysroot
            )

    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.safe_exec_with_redirect")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.os.rename")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.os.symlink")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.STORAGE")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.DeviceData")
    def dir_run_test(self, devdata_mock, storage_mock, symlink_mock, rename_mock, exec_mock):
        """Test OSTree bootloader config task, dirinstall"""
        proxy_mock = storage_mock.get_proxy()
        proxy_mock.GetArguments.return_value = ["BOOTLOADER-ARGS"]
        proxy_mock.GetFstabSpec.return_value = "FSTAB-SPEC"
        proxy_mock.GetRootDevice.return_value = "device-name"
        devdata_mock.from_structure.return_value.type = "something-non-btrfs-subvolume-ish"

        with tempfile.TemporaryDirectory() as sysroot:
            os.makedirs(sysroot + "/boot/grub2")
            os.mknod(sysroot + "/boot/grub2/grub.cfg")

            task = ConfigureBootloader(sysroot, is_dirinstall=True)
            task.run()

            rename_mock.assert_called_once_with(
                sysroot + "/boot/grub2/grub.cfg",
                sysroot + "/boot/loader/grub.cfg"
            )
            symlink_mock.assert_called_once_with(
                "../loader/grub.cfg",
                sysroot + "/boot/grub2/grub.cfg"
            )
            exec_mock.assert_not_called()


class DeployOSTreeTaskTestCase(unittest.TestCase):
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.safe_exec_with_redirect")
    def run_test(self, exec_mock):
        """Test OSTree deploy task"""
        data = _make_config_data()

        task = DeployOSTreeTask(data, "/sysroot")
        task.run()

        exec_mock.assert_has_calls([
            call("ostree", ["admin", "--sysroot=/sysroot", "os-init", "osname"]),
            call("ostree", ["admin", "--sysroot=/sysroot", "deploy", "--os=osname", "remote:ref"])
        ])
        # no need to mock RpmOstree.varsubst_basearch(), since "ref" won't change


class PullRemoteAndDeleteTaskTestCase(unittest.TestCase):
    # pylint: disable=unused-variable
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.create_new_context")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.OSTree.AsyncProgress.new")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.OSTree.Sysroot.new")
    def run_success_test(self, sysroot_new_mock, async_new_mock, context_mock):
        """Test OSTree remote pull task"""
        data = _make_config_data()

        sysroot_mock = sysroot_new_mock()
        repo_mock = MagicMock()
        sysroot_mock.get_repo.return_value = [None, repo_mock]

        with patch.object(PullRemoteAndDeleteTask, "report_progress") as progress_mock:
            task = PullRemoteAndDeleteTask(data)
            task.run()

        context_mock.assert_called_once()
        async_new_mock.assert_called_once()
        self.assertEqual(len(sysroot_new_mock.mock_calls), 4)
        # 1 above, 1 direct in run(), 2 on the result: load(), get_repo()

        repo_mock.pull_with_options.assert_called_once()
        name, args, kwargs = repo_mock.pull_with_options.mock_calls[0]
        opts = args[1]
        self.assertEqual(type(opts), Variant)
        self.assertDictEqual(
            opts.unpack(),
            {"refs": ["ref"]}
        )
        repo_mock.remote_delete.assert_called_once_with("remote", None)

    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.create_new_context")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.OSTree.AsyncProgress.new")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.OSTree.Sysroot.new")
    def run_failure_test(self, sysroot_new_mock, async_new_mock, context_mock):
        """Test OSTree remote pull task failure"""
        data = _make_config_data()

        sysroot_mock = sysroot_new_mock()
        repo_mock = MagicMock()
        sysroot_mock.get_repo.return_value = [None, repo_mock]
        repo_mock.pull_with_options.side_effect = [GError("blah")]

        with patch.object(PullRemoteAndDeleteTask, "report_progress") as progress_mock:
            with self.assertRaises(PayloadInstallError) as ex:
                task = PullRemoteAndDeleteTask(data)
                task.run()

        context_mock.assert_called_once()
        async_new_mock.assert_called_once()
        self.assertEqual(len(sysroot_new_mock.mock_calls), 4)
        # 1 above, 1 direct in run(), 2 on the result: load(), get_repo()

        repo_mock.pull_with_options.assert_called_once()
        name, args, kwargs = repo_mock.pull_with_options.mock_calls[0]
        opts = args[1]
        self.assertEqual(type(opts), Variant)
        self.assertDictEqual(
            opts.unpack(),
            {"refs": ["ref"]}
        )
        repo_mock.remote_delete.assert_not_called()

    def pull_progress_report_test(self):
        """Test OSTree remote pull task progress reporting"""
        data = _make_config_data()

        with patch.object(PullRemoteAndDeleteTask, "report_progress") as progress_mock:
            task = PullRemoteAndDeleteTask(data)
            async_mock = MagicMock()
            # Mocks below must use side_effect so as not to mix it with return_value.

            # status is present, outstanding fetches do not matter
            async_mock.get_status.return_value = "Doing something vague"
            async_mock.get_uint.side_effect = [0]
            task._pull_progress_cb(async_mock)
            progress_mock.assert_called_once_with("Doing something vague")
            progress_mock.reset_mock()
            async_mock.get_uint.reset_mock()

            # no status, no outstanding fetches
            async_mock.get_status.return_value = ""
            async_mock.get_uint.side_effect = [0]
            task._pull_progress_cb(async_mock)
            progress_mock.assert_called_once_with("Writing objects")
            progress_mock.reset_mock()
            async_mock.get_uint.reset_mock()

            # no status, some outstanding fetches
            async_mock.get_status.return_value = ""
            async_mock.get_uint.side_effect = [3, 10, 13]
            # 3 fetches outstanding, 10 done, requested 13
            async_mock.get_uint64.return_value = 42e3  # bytes transferred
            task._pull_progress_cb(async_mock)
            progress_mock.assert_called_once_with(
                "Receiving objects: 76% (10/13) 42.0\xa0kB"
            )
            progress_mock.reset_mock()
            async_mock.get_uint.reset_mock()

            # no status, some outstanding fetches, but also nothing requested
            async_mock.get_status.return_value = ""
            async_mock.get_uint.side_effect = [3, 10, 0]
            # 3 fetches outstanding, 10 done, requested 13
            async_mock.get_uint64.return_value = 42e3  # bytes transferred
            task._pull_progress_cb(async_mock)
            progress_mock.assert_called_once_with(
                "Receiving objects: 0% (10/0) 42.0\xa0kB"
            )


class SetSystemRootTaskTestCase(unittest.TestCase):
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.OSTree.Sysroot.new")
    @patch("pyanaconda.modules.payloads.payload.rpm_ostree.installation.set_system_root")
    def run_test(self, set_mock, new_sysroot_mock):
        """Test OSTree sysroot set task"""
        sysroot_mock = new_sysroot_mock()
        sysroot_mock.get_deployments.return_value = [None]

        task = SetSystemRootTask("/physroot")
        task.run()

        self.assertEqual(len(new_sysroot_mock.mock_calls), 2+4)
        # 2 above: new, get_deployments;
        # 4 in run(): new(), load(), get_deployments(), get_deployment_directory()
        set_mock.assert_called_once()
