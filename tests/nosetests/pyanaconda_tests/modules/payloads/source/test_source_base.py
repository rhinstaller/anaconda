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
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from pyanaconda.modules.common.errors.payload import SourceSetupError, SourceTearDownError
from pyanaconda.modules.payloads.constants import SourceType
from pyanaconda.modules.payloads.source.mount_tasks import SetUpMountTask, TearDownMountTask
from pyanaconda.modules.payloads.source.source_base import MountingSourceMixin
from pyanaconda.modules.payloads.source.utils import find_and_mount_iso_image, \
    verify_valid_repository

mount_location = "/some/dir"


class DummyMountingSourceSubclass(MountingSourceMixin):
    """Dummy class to test code in its abstract ancestor."""

    @property
    def type(self):
        return SourceType.URL


class DummySetUpMountTaskSubclass(SetUpMountTask):
    """Dummy class to test code in its abstract ancestor."""

    @property
    def name(self):
        return "Set up Dummy Installation Source"

    def _do_mount(self):
        pass


class MountingSourceMixinTestCase(unittest.TestCase):

    def counter_test(self):
        """Mount path in mount source base gets incremental numbers."""
        module = DummyMountingSourceSubclass()
        self.assertTrue(module.mount_point.startswith("/run/install/sources/mount-"))
        first_counter = int(module.mount_point.split("-")[1])

        module = DummyMountingSourceSubclass()
        second_counter = int(module.mount_point.split("-")[1])

        self.assertEqual(first_counter, second_counter - 1)

    @patch("os.path.ismount")
    def mount_state_test(self, ismount_mock):
        """Mount source state for set up."""
        ismount_mock.return_value = False
        module = DummyMountingSourceSubclass()
        self.assertEqual(False, module.get_mount_state())

        ismount_mock.reset_mock()
        ismount_mock.return_value = True

        self.assertEqual(True, module.get_mount_state())

        ismount_mock.assert_called_once_with(module.mount_point)


class TearDownMountTaskTestCase(unittest.TestCase):

    def name_test(self):
        """Tear down mount source task name."""
        task = TearDownMountTask(mount_location)
        self.assertEqual(task.name, "Tear down mount installation source")

    @patch("pyanaconda.modules.payloads.source.mount_tasks.os.path.ismount", return_value=False)
    @patch("pyanaconda.modules.payloads.source.mount_tasks.unmount", return_value=True)
    def run_success_test(self, unmount_mock, ismount_mock):
        """Tear down mount source task execution."""
        task = TearDownMountTask(mount_location)
        task.run()
        unmount_mock.assert_called_once_with(mount_location)
        ismount_mock.assert_called_once_with(mount_location)

    @patch("pyanaconda.modules.payloads.source.mount_tasks.os.path.ismount", return_value=True)
    @patch("pyanaconda.modules.payloads.source.mount_tasks.unmount", return_value=True)
    def run_failure_test(self, unmount_mock, ismount_mock):
        """Tear down mount source task failure."""
        task = TearDownMountTask(mount_location)
        with self.assertRaises(SourceTearDownError) as cm:
            task.run()

        self.assertEqual(str(cm.exception), "The mount point /some/dir is still in use.")
        unmount_mock.assert_called_once_with(mount_location)
        ismount_mock.assert_called_once_with(mount_location)


class SetUpMountTaskTestCase(unittest.TestCase):

    @patch("pyanaconda.modules.payloads.source.mount_tasks.os.path.ismount", return_value=False)
    def run_success_test(self, ismount_mock):
        """Set up mount base task success case."""
        task = DummySetUpMountTaskSubclass(mount_location)
        task.run()
        ismount_mock.assert_called_once_with(mount_location)

    @patch("pyanaconda.modules.payloads.source.mount_tasks.os.path.ismount", return_value=True)
    def run_failure_test(self, ismount_mock):
        """Set up mount base task when already mounted."""
        task = DummySetUpMountTaskSubclass(mount_location)
        with self.assertRaises(SourceSetupError) as cm:
            task.run()

        self.assertEqual(str(cm.exception), "The mount point /some/dir is already in use.")
        ismount_mock.assert_called_once_with(mount_location)


class UtilitiesTestCase(unittest.TestCase):

    @patch("pyanaconda.modules.payloads.source.utils.find_first_iso_image",
           return_value="skynet.iso")
    @patch("pyanaconda.modules.payloads.source.utils.mount")
    def find_and_mount_iso_image_test(self,
                                      mount_mock,
                                      find_first_iso_image_mock,):
        """Test find_and_mount_iso_image basic run."""
        source_path = "/super/cool/secret/base"
        mount_path = "/less/cool/secret/base"

        iso_name = find_and_mount_iso_image(source_path, mount_path)

        find_first_iso_image_mock.assert_called_once_with(source_path)
        mount_mock.assert_called_once_with(
            source_path + "/" + "skynet.iso",
            mount_path,
            fstype="iso9660",
            options="ro"
        )

        self.assertEqual(iso_name, "skynet.iso")

    @patch("pyanaconda.modules.payloads.source.utils.find_first_iso_image",
           return_value="")
    def find_and_mount_iso_image_fail_find_test(self,
                                                find_first_iso_image_mock,):
        """Test find_and_mount_iso_image failure to find iso."""
        source_path = "/super/cool/secret/base"
        mount_path = "/less/cool/secret/base"

        iso_name = find_and_mount_iso_image(source_path, mount_path)

        find_first_iso_image_mock.assert_called_once_with(source_path)

        self.assertEqual(iso_name, "")

    @patch("pyanaconda.modules.payloads.source.utils.find_first_iso_image",
           return_value="skynet.iso")
    @patch("pyanaconda.modules.payloads.source.utils.mount",
           side_effect=OSError)
    def find_and_mount_iso_image_fail_mount_test(self,
                                                 mount_mock,
                                                 find_first_iso_image_mock,):
        """Test find_and_mount_iso_image failure to mount iso."""
        source_path = "/super/cool/secret/base"
        mount_path = "/less/cool/secret/base"

        iso_name = find_and_mount_iso_image(source_path, mount_path)

        find_first_iso_image_mock.assert_called_once_with(source_path)
        mount_mock.assert_called_once_with(
            source_path + "/" + "skynet.iso",
            mount_path,
            fstype="iso9660",
            options="ro"
        )

        self.assertEqual(iso_name, "")

    def verify_valid_repository_repo_success_test(self):
        """Test verify_valid_repository functionality success."""
        with TemporaryDirectory() as tmp:
            repodir_path = Path(tmp, "repodata")
            repodir_path.mkdir()
            repomd_path = Path(repodir_path, "repomd.xml")
            repomd_path.write_text("This is a cool repomd file!")

            self.assertTrue(verify_valid_repository(tmp))

    def verify_valid_repository_installtree_success_test(self):
        """Test verify_valid_repository functionality for installation tree success."""
        with TemporaryDirectory() as tmp:
            treeinfo_path = Path(tmp, ".treeinfo")
            treeinfo_path.write_text("This is a cool .treeinfo file!")

            self.assertTrue(verify_valid_repository(tmp))

        with TemporaryDirectory() as tmp:
            treeinfo_path = Path(tmp, "treeinfo")
            treeinfo_path.write_text("This is a cool treeinfo file!")

            self.assertTrue(verify_valid_repository(tmp))

    def verify_valid_repository_failed_test(self):
        """Test verify_valid_repository functionality failed."""
        with TemporaryDirectory() as tmp:
            repodir_path = Path(tmp, "repodata")
            repodir_path.mkdir()

            self.assertFalse(verify_valid_repository(tmp))
