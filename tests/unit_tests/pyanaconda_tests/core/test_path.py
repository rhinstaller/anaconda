#
# Copyright (C) 2021  Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
import os
import shutil
import tempfile
import unittest
from unittest.mock import call, patch

import pytest

from pyanaconda.core.path import (
    copy_folder,
    get_mount_paths,
    join_paths,
    make_directories,
    open_with_perm,
    set_mode,
    set_system_root,
    touch,
)


class SetSystemRootTests(unittest.TestCase):
    """Test set_system_root"""

    @patch("pyanaconda.core.util.execWithRedirect")
    @patch("pyanaconda.core.path.make_directories")
    @patch("pyanaconda.core.path.conf")
    @patch("pyanaconda.core.path.os.path.exists")
    def test_success(self, exists_mock, conf_mock, mkdir_mock, exec_mock):
        """Test set_system_root_path success"""
        conf_mock.target.system_root = "/some/root"
        exec_mock.side_effect = [0, 0, 0, 0]
        exists_mock.return_value = True

        set_system_root("/other/root")  # note it's different from the conf target root

        exists_mock.assert_called_once_with("/some/root")
        mkdir_mock.assert_not_called()
        exec_mock.assert_has_calls([
            call("findmnt", ["-rn", "/some/root"]),
            call("mount", ["--make-rprivate", "/some/root"]),
            call("umount", ["--recursive", "/some/root"]),
            call("mount", ["--rbind", "/other/root", "/some/root"]),
        ])

    @patch("pyanaconda.core.util.execWithRedirect")
    @patch("pyanaconda.core.path.make_directories")
    @patch("pyanaconda.core.path.conf")
    @patch("pyanaconda.core.path.os.path.exists")
    def test_same(self, exists_mock, conf_mock, mkdir_mock, exec_mock):
        """Test set_system_root_path mount to same path"""
        conf_mock.target.system_root = "/same/root"
        exec_mock.side_effect = [0, 0, 0, 0]
        exists_mock.return_value = True

        set_system_root("/same/root")  # same as conf target root

        exists_mock.assert_not_called()
        mkdir_mock.assert_not_called()
        exec_mock.assert_not_called()

    @patch("pyanaconda.core.util.execWithRedirect")
    @patch("pyanaconda.core.path.make_directories")
    @patch("pyanaconda.core.path.conf")
    @patch("pyanaconda.core.path.os.path.exists")
    def test_alt(self, exists_mock, conf_mock, mkdir_mock, exec_mock):
        """Test set_system_root_path alternate code paths"""
        conf_mock.target.system_root = "/some/root"
        exec_mock.side_effect = [1, 0, 0, 0]
        exists_mock.return_value = False

        set_system_root("/other/root")

        exists_mock.assert_called_once_with("/some/root")
        mkdir_mock.assert_called_once_with("/some/root")
        exec_mock.assert_has_calls([
            call("findmnt", ["-rn", "/some/root"]),
            call("mount", ["--rbind", "/other/root", "/some/root"]),
        ])
        assert exec_mock.call_count == 2

    @patch("pyanaconda.core.util.execWithRedirect")
    @patch("pyanaconda.core.path.make_directories")
    @patch("pyanaconda.core.path.conf")
    @patch("pyanaconda.core.path.os.path.exists")
    def test_fail(self, exists_mock, conf_mock, mkdir_mock, exec_mock):
        """Test set_system_root_path failure"""
        conf_mock.target.system_root = "/some/root"
        exec_mock.side_effect = [0, 0, 0, 1]
        exists_mock.return_value = True

        with pytest.raises(OSError):
            set_system_root("/other/root")

        exists_mock.assert_called_once_with("/some/root")
        mkdir_mock.assert_not_called()
        exec_mock.assert_has_calls([
            call("findmnt", ["-rn", "/some/root"]),
            call("mount", ["--make-rprivate", "/some/root"]),
            call("umount", ["--recursive", "/some/root"]),
            call("mount", ["--rbind", "/other/root", "/some/root"]),
        ])

    @patch("pyanaconda.core.util.execWithRedirect")
    @patch("pyanaconda.core.path.make_directories")
    @patch("pyanaconda.core.path.conf")
    @patch("pyanaconda.core.path.os.path.exists")
    def test_noroot(self, exists_mock, conf_mock, mkdir_mock, exec_mock):
        """Test set_system_root_path with no root"""
        conf_mock.target.system_root = "/some/root"
        exec_mock.side_effect = [0, 0, 0, 0]
        exists_mock.return_value = True

        set_system_root(None)

        exists_mock.assert_not_called()
        mkdir_mock.assert_not_called()
        exec_mock.assert_has_calls([
            call("findmnt", ["-rn", "/some/root"]),
            call("mount", ["--make-rprivate", "/some/root"]),
            call("umount", ["--recursive", "/some/root"]),
        ])
        assert exec_mock.call_count == 3


class MiscTests(unittest.TestCase):

    def test_make_directories(self):
        """Test make_directories"""

        with tempfile.TemporaryDirectory() as tmpdir:

            # don't fail if directory path already exists
            make_directories('/')
            make_directories('/tmp')

            # create a path and test it exists
            test_folder = "test_mkdir_chain"
            test_paths = [
                "foo",
                "foo/bar/baz",
                "",
                "čřščščřščř",
                "asdasd asdasd",
                "! spam"
            ]

            # join with the toplevel test folder and the folder for this test
            test_paths = [os.path.join(str(tmpdir), test_folder, p)
                          for p in test_paths]

            # create the folders and check that they exist
            for p in test_paths:
                make_directories(p)
                assert os.path.exists(p)

            # try to create them again - all the paths should already exist
            # and the make_directories function needs to handle that
            # without a traceback
            for p in test_paths:
                make_directories(p)

    @patch("pyanaconda.core.path.open")
    @patch("pyanaconda.core.path.os.stat")
    def test_get_mount_paths(self, stat_mock, open_mock):
        """Test get_mount_paths"""
        stat_mock.return_value.st_rdev = 2049
        open_mock.return_value = [
            "92 59 253:3 / /home rw,relatime shared:45 - ext4 /dev/mapper/fedora_home rw,seclabel",
            "95 59 8:1 / /boot rw,relatime shared:47 - ext4 /dev/sda1 rw,seclabel",
            "95 59 8:1 / /mnt/blah rw,relatime shared:47 - ext4 /dev/sda1 ro",
            "146 59 0:38 / /var/lib/nfs/rpc_pipefs rw,relatime shared:73 - rpc_pipefs sunrpc rw",
        ]
        assert get_mount_paths("/dev/sda1") == ["/boot", "/mnt/blah"]

        open_mock.return_value = ""
        assert get_mount_paths("/dev/sda1") == []

    def test_open_with_perm(self):
        """Test the open_with_perm function"""
        # Create a directory for test files
        test_dir = tempfile.mkdtemp()
        try:
            # Reset the umask
            old_umask = os.umask(0)
            try:
                # Create a file with mode 0777
                open_with_perm(test_dir + '/test1', 'w', 0o777)
                assert os.stat(test_dir + '/test1').st_mode & 0o777 == 0o777

                # Create a file with mode 0600
                open_with_perm(test_dir + '/test2', 'w', 0o600)
                assert os.stat(test_dir + '/test2').st_mode & 0o777 == 0o600
            finally:
                os.umask(old_umask)
        finally:
            shutil.rmtree(test_dir)

    def test_join_paths(self):
        """Test join_paths"""
        assert join_paths("/first/path/") == \
            "/first/path/"
        assert join_paths("") == \
            ""
        assert join_paths("/first/path/", "/second/path") == \
            "/first/path/second/path"
        assert join_paths("/first/path/", "/second/path", "/third/path") == \
            "/first/path/second/path/third/path"
        assert join_paths("/first/path/", "/second/path", "third/path") == \
            "/first/path/second/path/third/path"
        assert join_paths("/first/path/", "second/path") == \
            "/first/path/second/path"
        assert join_paths("first/path", "/second/path") == \
            "first/path/second/path"
        assert join_paths("first/path", "second/path") == \
            "first/path/second/path"

    def test_touch(self):
        """Test if the touch function correctly creates empty files"""
        test_dir = tempfile.mkdtemp()
        try:
            file_path = os.path.join(test_dir, "EMPTY_FILE")
            # try to create an empty file with touch()
            touch(file_path)

            # check if it exists & is a file
            assert os.path.isfile(file_path)

            # check if the file is empty
            assert os.stat(file_path).st_size == 0
        finally:
            shutil.rmtree(test_dir)

    def test_set_mode(self):
        """Test if the set_mode function"""
        test_dir = tempfile.mkdtemp()
        try:
            file_path = os.path.join(test_dir, "EMPTY_FILE")

            # test default mode - file will be created when it doesn't exists
            set_mode(file_path)

            # check if it exists & is a file
            assert os.path.isfile(file_path)
            # check if the file is empty
            assert os.stat(file_path).st_mode == 0o100600

            # test change of mode on already created file
            set_mode(file_path, 0o744)

            # check if the file is empty
            assert os.stat(file_path).st_mode == 0o100744
        finally:
            shutil.rmtree(test_dir)

    def test_copy_folder(self):
        """Test copy_folder function"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # create source folder with content
            source_folder = os.path.join(tmpdir, "source")
            os.makedirs(source_folder)
            test_file = os.path.join(source_folder, "test.txt")
            with open(test_file, "w") as f:
                f.write("test content")

            # create nested folder
            nested_folder = os.path.join(source_folder, "nested")
            os.makedirs(nested_folder)
            nested_file = os.path.join(nested_folder, "nested.txt")
            with open(nested_file, "w") as f:
                f.write("nested content")

            # copy to target
            target_folder = os.path.join(tmpdir, "target")
            result = copy_folder(source_folder, target_folder)

            # verify success
            assert result
            assert os.path.isdir(target_folder)
            assert os.path.isfile(os.path.join(target_folder, "test.txt"))
            assert os.path.isfile(os.path.join(target_folder, "nested", "nested.txt"))
            # verify content
            with open(os.path.join(target_folder, "test.txt"), "r") as f:
                assert f.read() == "test content"
            with open(os.path.join(target_folder, "nested", "nested.txt"), "r") as f:
                assert f.read() == "nested content"

    def test_copy_folder_nonexistent(self):
        """Test copy_folder with non-existent source"""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_folder = os.path.join(tmpdir, "nonexistent")
            target_folder = os.path.join(tmpdir, "target")

            result = copy_folder(source_folder, target_folder)

            assert result is False
            assert not os.path.exists(target_folder)

    def test_copy_folder_dirs_exist_ok(self):
        """Test copy_folder overwrites existing directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # create source folder
            source_folder = os.path.join(tmpdir, "source")
            os.makedirs(source_folder)
            with open(os.path.join(source_folder, "file.txt"), "w") as f:
                f.write("new content")

            # create existing target with different content
            target_folder = os.path.join(tmpdir, "target")
            os.makedirs(target_folder)
            with open(os.path.join(target_folder, "file.txt"), "w") as f:
                f.write("old content")

            result = copy_folder(source_folder, target_folder)

            assert result
            with open(os.path.join(target_folder, "file.txt"), "r") as f:
                assert f.read() == "new content"
