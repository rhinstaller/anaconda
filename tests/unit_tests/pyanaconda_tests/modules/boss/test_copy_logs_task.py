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
from unittest.mock import call, patch
from pyanaconda.modules.boss.installation import CopyLogsTask


class CopyLogsTaskTest(unittest.TestCase):
    @patch("pyanaconda.modules.boss.installation.glob.glob")
    @patch("pyanaconda.modules.boss.installation.execWithRedirect")
    @patch("pyanaconda.modules.boss.installation.mkdirChain")
    @patch("pyanaconda.modules.boss.installation.conf")
    @patch("pyanaconda.modules.boss.installation.open")
    @patch("pyanaconda.modules.boss.installation.os.chmod")
    def test_run_all(self, chmod_mock, open_mock, conf_mock, mkdir_mock, exec_wr_mock, glob_mock):
        """Test the log copying task."""
        glob_mock.side_effect = [
            ["/tmp/ks-script-blabbityblah.log"],
            ["/somewhere/var/log/anaconda/anaconda.log"]
        ]
        conf_mock.target.can_save_installation_logs = True
        conf_mock.target.can_copy_input_kickstart = True

        task = CopyLogsTask("/somewhere")
        with patch.object(CopyLogsTask, "_copy_file_to_sysroot") as copy_file_mock:
            with patch.object(CopyLogsTask, "_copy_tree_to_sysroot") as copy_tree_mock:
                task.run()

        mkdir_mock.assert_called_once_with("/somewhere/var/log/anaconda/")

        for logfile in ["anaconda.log", "syslog", "X.log", "program.log", "packaging.log",
                        "storage.log", "ifcfg.log", "lvm.log", "dnf.librepo.log", "hawkey.log",
                        "dbus.log"]:
            copy_file_mock.assert_any_call(
                "/tmp/"+logfile,
                "/var/log/anaconda/" + logfile
            )

        copy_file_mock.assert_any_call(
            "/root/lorax-packages.log",
            "/var/log/anaconda/lorax-packages.log"
        )

        copy_file_mock.assert_any_call(
            "/tmp/ks-script-blabbityblah.log",
            "/var/log/anaconda/ks-script-blabbityblah.log"
        )

        copy_tree_mock.assert_has_calls([
            call("/tmp/pre-anaconda-logs", "/var/log/anaconda/"),
            call("/root/debugdata", "/var/log/anaconda/dnf_debugdata/")
        ])

        glob_mock.assert_has_calls([
            call("/tmp/ks-script*.log"),
            call("/somewhere/var/log/anaconda/*")
        ])
        chmod_mock.assert_has_calls([
            call("/somewhere/var/log/anaconda/anaconda.log", 0o0600),
            call("/somewhere/root/original-ks.cfg", 0o0600)
        ])
        open_mock.assert_called_once_with("/somewhere/var/log/anaconda/journal.log", "w")

        exec_wr_mock.assert_has_calls([
            # Warning: Constructing the argument to the first call requires a call to one of the
            # mocks, altering its history. Any asserts about it should happen before this.
            call("journalctl", ["-b"], stdout=open_mock().__enter__.return_value),
            call("restorecon", ["-ir", "/var/log/anaconda/"], root="/somewhere")
        ])
        assert exec_wr_mock.call_count == 2

    @patch("pyanaconda.modules.boss.installation.glob.glob")
    @patch("pyanaconda.modules.boss.installation.execWithRedirect")
    @patch("pyanaconda.modules.boss.installation.mkdirChain")
    @patch("pyanaconda.modules.boss.installation.conf")
    @patch("pyanaconda.modules.boss.installation.open")
    @patch("pyanaconda.modules.boss.installation.os.chmod")
    def test_nosave_logs(self, chmod_mock, open_mock, conf_mock, mkdir_mock, exec_wr_mock,
                         glob_mock):
        """Test nosave for logs"""
        glob_mock.return_value = []
        conf_mock.target.can_save_installation_logs = False
        conf_mock.target.can_copy_input_kickstart = True

        task = CopyLogsTask("/somewhere")
        with patch.object(CopyLogsTask, "_copy_file_to_sysroot") as copy_file_mock:
            with patch.object(CopyLogsTask, "_copy_tree_to_sysroot") as copy_tree_mock:
                task.run()

        copy_file_mock.assert_called_once_with("/run/install/ks.cfg", "/root/original-ks.cfg")
        chmod_mock.assert_called_once_with("/somewhere/root/original-ks.cfg", 0o0600)

        exec_wr_mock.assert_called_once_with(
            "restorecon",
            ["-ir", "/var/log/anaconda/"],
            root="/somewhere"
        )

        mkdir_mock.assert_not_called()
        glob_mock.assert_not_called()
        copy_tree_mock.assert_not_called()
        open_mock.assert_not_called()

    @patch("pyanaconda.modules.boss.installation.glob.glob")
    @patch("pyanaconda.modules.boss.installation.execWithRedirect")
    @patch("pyanaconda.modules.boss.installation.mkdirChain")
    @patch("pyanaconda.modules.boss.installation.conf")
    @patch("pyanaconda.modules.boss.installation.open")
    @patch("pyanaconda.modules.boss.installation.os.chmod")
    def test_nosave_input_ks(self, chmod_mock, open_mock, conf_mock, mkdir_mock, exec_wr_mock,
                             glob_mock):
        """Test nosave for kickstart"""
        glob_mock.return_value = ["/somewhere/var/log/anaconda/anaconda.log"]
        conf_mock.target.can_save_installation_logs = True
        conf_mock.target.can_copy_input_kickstart = False

        task = CopyLogsTask("/somewhere")
        with patch.object(CopyLogsTask, "_copy_file_to_sysroot") as copy_file_mock:
            with patch.object(CopyLogsTask, "_copy_tree_to_sysroot") as copy_tree_mock:
                task.run()

        mkdir_mock.assert_called_once_with("/somewhere/var/log/anaconda/")

        assert call("/run/install/ks.cfg", "/root/original-ks.cfg") \
               not in copy_file_mock.call_args_list

        assert copy_tree_mock.called
        assert exec_wr_mock.called
        assert glob_mock.called
        assert open_mock.called
        assert chmod_mock.called

    @patch("pyanaconda.modules.boss.installation.glob.glob")
    @patch("pyanaconda.modules.boss.installation.execWithRedirect")
    @patch("pyanaconda.modules.boss.installation.mkdirChain")
    @patch("pyanaconda.modules.boss.installation.conf")
    @patch("pyanaconda.modules.boss.installation.open")
    @patch("pyanaconda.modules.boss.installation.os.chmod")
    def test_nosave_logs_and_input_ks(self, chmod_mock, open_mock, conf_mock, mkdir_mock,
                                      exec_wr_mock, glob_mock):
        """Test nosave for both logs and kickstart"""
        glob_mock.return_value = []
        conf_mock.target.can_save_installation_logs = False
        conf_mock.target.can_copy_input_kickstart = False

        task = CopyLogsTask("/somewhere")
        with patch.object(CopyLogsTask, "_copy_file_to_sysroot") as copy_file_mock:
            with patch.object(CopyLogsTask, "_copy_tree_to_sysroot") as copy_tree_mock:
                task.run()

        # contexts are always restored, but that's the only call this time
        exec_wr_mock.assert_called_once_with(
            "restorecon",
            ["-ir", "/var/log/anaconda/"],
            root="/somewhere"
        )

        mkdir_mock.assert_not_called()
        glob_mock.assert_not_called()
        copy_file_mock.assert_not_called()
        copy_tree_mock.assert_not_called()
        open_mock.assert_not_called()
        chmod_mock.assert_not_called()

    @patch("pyanaconda.modules.boss.installation.shutil.copyfile")
    @patch("pyanaconda.modules.boss.installation.os.path.exists")
    def test_copy_file_to_sysroot(self, exists_mock, copyfile_mock):
        """Test _copy_file_to_sysroot"""
        task = CopyLogsTask("/somewhere")

        exists_mock.return_value = True
        task._copy_file_to_sysroot("/some/source", "/another/destination")
        exists_mock.assert_called_with("/some/source")
        copyfile_mock.assert_called_with("/some/source", "/somewhere/another/destination")

        exists_mock.reset_mock()
        copyfile_mock.reset_mock()

        exists_mock.return_value = False
        task._copy_file_to_sysroot("/more/data", "/there")
        exists_mock.assert_called_with("/more/data")
        copyfile_mock.assert_not_called()

    @patch("pyanaconda.modules.boss.installation.shutil.copytree")
    @patch("pyanaconda.modules.boss.installation.os.path.exists")
    def test_copy_tree_to_sysroot(self, exists_mock, copytree_mock):
        """Test _copy_tree_to_sysroot"""
        task = CopyLogsTask("/somewhere")

        exists_mock.return_value = True
        task._copy_tree_to_sysroot("/some/source", "/another/destination/")
        exists_mock.assert_called_with("/some/source")
        copytree_mock.assert_called_with(
            "/some/source",
            "/somewhere/another/destination/",
            dirs_exist_ok=True
        )

        exists_mock.reset_mock()
        copytree_mock.reset_mock()

        exists_mock.return_value = False
        task._copy_tree_to_sysroot("/more/data", "/there")
        exists_mock.assert_called_with("/more/data")
        copytree_mock.assert_not_called()