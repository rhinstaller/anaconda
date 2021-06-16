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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import os
from tempfile import TemporaryDirectory

import unittest

from pyanaconda.core.constants import SOURCE_TYPE_REPO_FILES
from pyanaconda.modules.common.errors.payload import SourceSetupError
from pyanaconda.modules.payloads.constants import SourceType
from pyanaconda.modules.payloads.source.repo_files.repo_files import RepoFilesSourceModule
from pyanaconda.modules.payloads.source.repo_files.repo_files_interface import \
    RepoFilesSourceInterface
from pyanaconda.modules.payloads.source.repo_files.initialization import \
    SetUpRepoFilesSourceTask


class RepoFilesSourceInterfaceTestCase(unittest.TestCase):

    def setUp(self):
        self.module = RepoFilesSourceModule()
        self.interface = RepoFilesSourceInterface(self.module)

    def test_type(self):
        """Test Repo files source has a correct type specified."""
        self.assertEqual(SOURCE_TYPE_REPO_FILES, self.interface.Type)

    def test_description(self):
        """Test NFS source description."""
        self.assertEqual("Local repositories", self.interface.Description)


class RepoFilesSourceTestCase(unittest.TestCase):

    def setUp(self):
        self.module = RepoFilesSourceModule()
        self.interface = RepoFilesSourceInterface(self.module)

    def test_type(self):
        """Test Repo files source module has a correct type."""
        self.assertEqual(SourceType.REPO_FILES, self.module.type)

    def test_network_required(self):
        """Test the property network_required."""
        self.assertEqual(self.module.network_required, True)

    def test_required_space(self):
        """Test the required_space property."""
        self.assertEqual(self.module.required_space, 0)

    def test_repr(self):
        self.assertEqual(repr(self.module), "Source(type='REPO_FILES')")

    def test_set_up_with_tasks(self):
        """Test Repo files Source set up call."""
        tasks = self.module.set_up_with_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertIsInstance(tasks[0], SetUpRepoFilesSourceTask)

    def test_tear_down_with_tasks(self):
        """Test Repo files Source ready state for tear down."""
        tasks = self.module.tear_down_with_tasks()
        self.assertEqual([], tasks)

    def test_ready_state(self):
        """Test Repo files Source ready state for set up."""
        self.assertTrue(self.module.get_state())


class RepoFilesSourceSetupTaskTestCase(unittest.TestCase):

    def test_setup_install_source_task_name(self):
        """Test Repo files Source setup installation source task name."""
        task = SetUpRepoFilesSourceTask([""])
        self.assertEqual(task.name, "Set up Repo files Installation Source")

    def test_setup_install_source_task_success(self):
        with TemporaryDirectory() as temp_dir_name:
            open(os.path.join(temp_dir_name, "somefile.repo"), "w").close()
            SetUpRepoFilesSourceTask([temp_dir_name]).run()

    def test_setup_install_source_task_failure(self):
        with TemporaryDirectory() as temp_dir_name:
            with self.assertRaises(SourceSetupError, msg="repo files not found"):
                SetUpRepoFilesSourceTask([temp_dir_name]).run()
