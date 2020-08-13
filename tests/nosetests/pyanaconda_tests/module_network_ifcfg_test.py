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
# Red Hat Author(s): Radek Vykydal <rvykydal@redhat.com>
#
import unittest
from unittest.mock import Mock, patch
import tempfile
import shutil
import os
from textwrap import dedent

from pyanaconda.modules.network.ifcfg import IFCFG_DIR, get_ifcfg_files_paths


class IfcfgFileTestCase(unittest.TestCase):

    def setUp(self):
        self._root_dir = tempfile.mkdtemp(prefix="ifcfg-test-dir")
        self._ifcfg_dir = os.path.join(self._root_dir, IFCFG_DIR.lstrip("/"))
        os.makedirs(self._ifcfg_dir)

    def tearDown(self):
        shutil.rmtree(self._root_dir)

    def _dump_ifcfg_files(self, files_list):
        for file_name, content, _generated_ks in files_list:
            content = dedent(content).strip()
            with open(os.path.join(self._ifcfg_dir, file_name), "w") as f:
                f.write(content)

    def _get_ifcfg_file_path(self, file_name):
        return os.path.join(self._ifcfg_dir, file_name)

    def get_ifcfg_files_paths_test(self):
        """Test get_ifcfg_files_paths."""
        all_ifcfg_files = [
            ("ifcfg-ens3",
             """
             DEVICE="ens3"
             """,
             None),
            ("ifcfg-ens5",
             """
             DEVICE="ens5"
             """,
             None),
            ("ifcfg-lo",
             """
             DEVICE="lo"
             """,
             None),
            ("nonifcfg",
             """
             Lebenswelt
             """,
             None),
        ]
        self._dump_ifcfg_files(all_ifcfg_files)
        ifcfg_paths = get_ifcfg_files_paths(self._ifcfg_dir)
        self.assertEqual(len(ifcfg_paths), 2)
        ifcfg_files = [os.path.basename(path) for path in ifcfg_paths]
        self.assertIn("ifcfg-ens3", ifcfg_files)
        self.assertIn("ifcfg-ens5", ifcfg_files)
