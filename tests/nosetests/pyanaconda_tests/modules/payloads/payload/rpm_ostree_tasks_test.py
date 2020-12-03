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
from unittest.mock import patch, call

from pyanaconda.modules.common.structures.rpm_ostree import RPMOSTreeConfigurationData

from pyanaconda.modules.payloads.payload.rpm_ostree.installation import \
    PrepareOSTreeMountTargetsTask, CopyBootloaderDataTask


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
