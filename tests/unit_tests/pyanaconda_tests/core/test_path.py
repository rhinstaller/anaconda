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
import tempfile
import unittest
from unittest.mock import patch, call
import pytest
from pyanaconda.core.path import set_system_root, make_directories


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
