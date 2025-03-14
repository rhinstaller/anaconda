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
# Red Hat Author(s): Radek Vykydal <rvykydal@redhat.com>
#
import os
import shutil
import tempfile
import unittest
from textwrap import dedent
from unittest.mock import patch

from pyanaconda.modules.network.config_file import (
    IFCFG_DIR,
    KEYFILE_DIR,
    get_config_files_content,
    get_config_files_paths,
    is_config_file_for_system,
)


class ConfigFileTestCase(unittest.TestCase):

    def setUp(self):
        self._root_dir = tempfile.mkdtemp(prefix="config-test-dir")

    def tearDown(self):
        shutil.rmtree(self._root_dir)

    def _dump_files(self, files_list, root_path=""):
        for file_path, content in files_list:
            file_path = os.path.normpath(root_path + file_path)
            file_dir = os.path.dirname(file_path)
            if not os.path.isdir(file_dir):
                os.makedirs(file_dir)
            content = dedent(content).strip()
            with open(file_path, "w") as f:
                print("Dumping{}".format(file_path))
                f.write(content)

    def test_get_config_files_paths(self):
        """Test get_config_files_paths."""
        IFCFG_FILE_1 = os.path.join(IFCFG_DIR, "ifcfg-ens3")
        IFCFG_FILE_2 = os.path.join(IFCFG_DIR, "ifcfg-ens5")
        KEYFILE_1 = os.path.join(KEYFILE_DIR, "ens7.nmconnection")
        KEYFILE_2 = os.path.join(KEYFILE_DIR, "ens8.nmconnection")
        all_files = [
            (IFCFG_FILE_1,
             """
             DEVICE="ens3"
             """),
            (IFCFG_FILE_2,
             """
             DEVICE="ens5"
             """),
            (os.path.join(IFCFG_DIR, "ifcfg-lo"),
             """
             DEVICE="lo"
             """),
            (os.path.join(IFCFG_DIR, "not-ifcfg-config"),
             """
             not-ifcfg-config content
             """),
            (KEYFILE_1,
             """
             keyfile-ens7-content
             """),
            (KEYFILE_2,
             """
             keyfile-ens8-content
             """),
            (os.path.join(KEYFILE_DIR, "ens9.not-config"),
             """
             ens9.not-config content
             """),
            ("/etc/foo/bar",
             """
             foo-bar-content
             """),
        ]
        self._dump_files(all_files, root_path=self._root_dir)
        assert set(get_config_files_paths(root_path=self._root_dir)) == \
            set([
                os.path.normpath(self._root_dir + IFCFG_FILE_1),
                os.path.normpath(self._root_dir + IFCFG_FILE_2),
                os.path.normpath(self._root_dir + KEYFILE_1),
                os.path.normpath(self._root_dir + KEYFILE_2),
            ])

    @patch("pyanaconda.modules.network.config_file.get_config_files_paths")
    def test_get_config_files_content(self, get_config_files_paths_mock):
        """Test get_config_files_content."""
        files = [
            ("/file1",
             """
             content1
             """),
            ("/dir/file2",
             """
             content2
             """),
        ]
        expected_content = """
        {}/file1:
        content1
        {}/dir/file2:
        content2
        """.format(self._root_dir, self._root_dir)
        self._dump_files(files, root_path=self._root_dir)

        get_config_files_paths_mock.return_value = [
            "{}/file1".format(self._root_dir),
            "{}/dir/file2".format(self._root_dir),
        ]
        content = get_config_files_content(self._root_dir)
        assert dedent(content).strip() == dedent(expected_content).strip()

    def test_is_config_file_for_system(self):
        """Test is_config_file_for_system function."""
        assert is_config_file_for_system(os.path.join(KEYFILE_DIR, "ens3.nmconnection"))
        assert is_config_file_for_system(os.path.join(IFCFG_DIR, "ifcfg-ens5"))
        assert not is_config_file_for_system("foo/bar")
        assert not is_config_file_for_system("/run/NetworkManager/system-connections/ens3.nmconnection")
        assert not is_config_file_for_system(os.path.join(IFCFG_DIR, "ifcfg-lo"))
        assert not is_config_file_for_system(os.path.join(KEYFILE_DIR, "ens3"))
