# Handle task category reporting.
#
# Copyright (C) 2024 Red Hat, Inc.
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
import unittest
from unittest.mock import Mock, call

from pyanaconda.core.constants import CATEGORY_STORAGE, CATEGORY_SYSTEM
from pyanaconda.installation_tasks import Task, TaskQueue
from pyanaconda.modules.boss.installation import RunInstallationTask


class TestRunInstallation(RunInstallationTask):

    def _prepare_configuration(self):
        configuration_queue = TaskQueue("Configuration queue")

        # connect progress reporting
        configuration_queue.queue_started.connect(self._queue_started_cb)
        configuration_queue.task_completed.connect(self._task_completed_cb)

        # Creating task queues with categories
        queue1 = TaskQueue(name="group2", task_category=CATEGORY_STORAGE)
        task1 = Task("Test task 2", lambda: None)
        queue1.append(task1)

        configuration_queue.append(queue1)

        return configuration_queue

    def _prepare_installation(self):
        installation_queue = TaskQueue("Installation queue")

        # connect progress reporting
        installation_queue.queue_started.connect(self._queue_started_cb)
        installation_queue.task_completed.connect(self._task_completed_cb)

        # Creating task queues with categories
        queue1 = TaskQueue(name="group1", task_category=CATEGORY_SYSTEM)
        task1 = Task("Test task 1", lambda: None)
        queue1.append(task1)

        installation_queue.append(queue1)

        return installation_queue


class InstallManagerTestCase(unittest.TestCase):
    """Test the install category API"""

    def test_task_category_reporting(self):
        install_manager = Mock()
        task = TestRunInstallation(install_manager)
        interface = task.for_publication()

        callback = Mock()
        # pylint: disable=no-member
        interface.CategoryChanged.connect(callback)
        task.run()

        callback.assert_has_calls([
            call(CATEGORY_SYSTEM),
            call(CATEGORY_STORAGE),
        ])
