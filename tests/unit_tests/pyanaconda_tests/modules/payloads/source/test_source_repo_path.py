#
# Copyright (C) 2023  Red Hat, Inc.
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
import subprocess
import unittest
import pytest

from tempfile import TemporaryDirectory

from pyanaconda.core.constants import SOURCE_TYPE_REPO_PATH
from pyanaconda.modules.common.constants.interfaces import PAYLOAD_SOURCE_REPO_PATH
from pyanaconda.modules.payloads.constants import SourceType, SourceState
from pyanaconda.modules.payloads.source.repo_path.repo_path import RepoPathSourceModule
from pyanaconda.modules.payloads.source.repo_path.repo_path_interface import \
    RepoPathSourceInterface
from pyanaconda.modules.payloads.source.repo_path.initialization import SetUpRepoPathSourceTask
from pyanaconda.modules.common.errors.payload import SourceSetupError

from tests.unit_tests.pyanaconda_tests import check_dbus_property


class RepoPathSourceInterfaceTestCase(unittest.TestCase):
    """Test the DBus interface of the repo path source."""

    def setUp(self):
        """Set up the test."""
        self.module = RepoPathSourceModule()
        self.interface = RepoPathSourceInterface(self.module)

    def _check_dbus_property(self, *args, **kwargs):
        check_dbus_property(
            PAYLOAD_SOURCE_REPO_PATH,
            self.interface,
            *args, **kwargs
        )

    def test_type(self):
        """Test the source type."""
        assert SOURCE_TYPE_REPO_PATH == self.interface.Type

    def test_description(self):
        """Test the source description."""
        assert self.interface.Description == "Auto-detected source"

    def test_path(self):
        """Test the Path property of the source."""
        self._check_dbus_property(
            "Path",
            "/repo/path"
        )


class RepoPathSourceTestCase(unittest.TestCase):
    """Test the repo path source."""

    def setUp(self):
        """Set up the test."""
        self.module = RepoPathSourceModule()

    def test_type(self):
        """Test the type property."""
        assert SourceType.REPO_PATH == self.module.type

    def test_network_required(self):
        """Test the network_required property."""
        assert self.module.network_required is False

    def test_required_space(self):
        """Test the required_space property."""
        assert self.module.required_space == 0

    def test_state(self):
        """Test repo path source state."""
        assert SourceState.NOT_APPLICABLE == self.module.get_state()

    def test_set_up_with_tasks(self):
        """Test repo path source set up call."""
        task_classes = [
            SetUpRepoPathSourceTask
        ]

        # task will not be public so it won't be published
        tasks = self.module.set_up_with_tasks()

        # Check the number of the tasks
        task_number = len(task_classes)
        assert task_number == len(tasks)

        for i in range(task_number):
            assert isinstance(tasks[i], task_classes[i])

    def test_tear_down_with_tasks(self):
        """Test repo path source tear down tasks."""
        assert self.module.tear_down_with_tasks() == []

    def test_repr(self):
        """Test repo path source repr call."""
        self.module.set_path("/repo/path")

        expected = "Source(type='REPO_PATH', path='/repo/path')"
        assert repr(self.module) == expected


class RepoPathSourceSetupTaskTestCase(unittest.TestCase):
    """Test the setup tasks of the repo path source."""

    def test_setup_install_source_task_name(self):
        """Test repo path source setup installation source task name."""
        task = SetUpRepoPathSourceTask("/repo/path")
        assert task.name == "Set up a local path to a repository"

    def test_verify_repository_success(self):
        """Test repo path source setup have valid repository."""
        with TemporaryDirectory() as path:
            subprocess.run(["createrepo_c", path], check=True)

            task = SetUpRepoPathSourceTask(path)
            task.run()

    def test_verify_repository_failure(self):
        """Test repo path source setup have invalid repository."""
        with TemporaryDirectory() as path:
            task = SetUpRepoPathSourceTask(path)

            with pytest.raises(SourceSetupError):
                task.run()
