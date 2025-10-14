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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Jiri Konecny <jkonecny@redhat.com>
#
import unittest
from unittest.mock import Mock, patch

from pyanaconda.modules.payloads.payload.flatpak.initialization import CalculateFlatpaksSizeTask
from pyanaconda.modules.payloads.payload.flatpak.installation import (
    CleanUpDownloadLocationTask,
    DownloadFlatpaksTask,
    InstallFlatpaksTask,
    PrepareDownloadLocationTask,
)


class CalculateFlatpaksSizeTaskTestCase(unittest.TestCase):
    """Test the CalculateFlatpaksSizeTask task."""

    def test_calculate_flatpaks_size_task_name(self):
        """Test CalculateFlatpaksSizeTask name."""
        flatpak_manager = Mock()
        task = CalculateFlatpaksSizeTask(flatpak_manager)

        assert task.name == "Calculate needed space for Flatpaks"

    def test_calculate_flatpaks_size_task_run(self):
        """Test CalculateFlatpaksSizeTask run."""
        flatpak_manager = Mock()

        task = CalculateFlatpaksSizeTask(flatpak_manager)
        task.run()

        flatpak_manager.calculate_size.assert_called_once()


class PrepareDownloadLocationTaskTestCase(unittest.TestCase):
    """Test PrepareDownloadLocationTask task."""

    def test_prepare_download_location_task_name(self):
        """Test PrepareDownloadLocationTask name."""
        flatpak_manager = Mock()
        task = PrepareDownloadLocationTask(flatpak_manager)
        assert task.name == "Prepare the Flatpaks download"

    @patch("pyanaconda.modules.payloads.payload.flatpak.installation.shutil")
    @patch("pyanaconda.modules.payloads.payload.flatpak.installation.os")
    @patch("pyanaconda.modules.payloads.payload.flatpak.installation.pick_download_location")
    def test_prepare_download_location_task_run(self,
                                                pick_download_location,
                                                os_mock,
                                                shutil_mock):
        """Test PrepareDownloadLocationTask run."""
        flatpak_manager = Mock()
        flatpak_manager.download_size = 10
        flatpak_manager.install_size = 20
        pick_download_location.return_value = "/result/path"

        # test path exists
        os_mock.path.exists.return_value = True
        task = PrepareDownloadLocationTask(flatpak_manager)
        path = task.run()

        assert path == "/result/path"
        flatpak_manager.calculate_size.assert_called_once()
        pick_download_location.assert_called_once_with(10, 20, 'flatpak.mirror')
        shutil_mock.rmtree.assert_called_once_with("/result/path")
        flatpak_manager.set_download_location.assert_called_once_with("/result/path")

        # test path doesn't exists
        os_mock.path.exists.return_value = False
        flatpak_manager.calculate_size.reset_mock()
        pick_download_location.reset_mock()
        shutil_mock.rmtree.reset_mock()
        flatpak_manager.set_download_location.reset_mock()

        task = PrepareDownloadLocationTask(flatpak_manager)
        path = task.run()

        assert path == "/result/path"
        pick_download_location.assert_called_once_with(10, 20, 'flatpak.mirror')
        shutil_mock.rmtree.assert_not_called()
        flatpak_manager.set_download_location.assert_called_once_with("/result/path")


class CleanUpDownloadLocationTaskTestCase(unittest.TestCase):
    """Test the CleanUpDownloadLocationTask task."""

    def test_clean_up_download_location_task_name(self):
        """Test CleanUpDownloadLocationTask name."""
        flatpak_manager = Mock()
        task = CleanUpDownloadLocationTask(flatpak_manager)

        assert task.name == "Remove downloaded Flatpaks"

    @patch("pyanaconda.modules.payloads.payload.flatpak.installation.shutil")
    @patch("pyanaconda.modules.payloads.payload.flatpak.installation.os")
    def test_clean_up_download_location_task_run(self, os_mock, shutil_mock):
        """Test CleanUpDownloadLocationTask run."""
        flatpak_manager = Mock()
        flatpak_manager.download_location = "/result/path"

        # test path exists - flatpaks were downloaded
        os_mock.path.exists.return_value = True
        task = CleanUpDownloadLocationTask(flatpak_manager)
        task.run()

        shutil_mock.rmtree.assert_called_once_with("/result/path")

        # test path doesn't exists - flatpaks were not downloaded
        shutil_mock.rmtree.reset_mock()

        os_mock.path.exists.return_value = False
        task = CleanUpDownloadLocationTask(flatpak_manager)
        task.run()

        shutil_mock.rmtree.assert_not_called()


class DownloadFlatpaksTaskTestCase(unittest.TestCase):
    """Test the DownloadFlatpaksTask task."""

    def test_clean_up_download_location_task_name(self):
        """Test DownloadFlatpaksTask name."""
        flatpak_manager = Mock()
        task = DownloadFlatpaksTask(flatpak_manager)

        assert task.name == "Download remote Flatpaks"

    def test_clean_up_download_location_task_run(self):
        """Test DownloadFlatpaksTask run."""
        flatpak_manager = Mock()

        task = DownloadFlatpaksTask(flatpak_manager)
        task.run()

        flatpak_manager.download.assert_called_once()


class InstallFlatpaksTaskTestCase(unittest.TestCase):
    """Test the InstallFlatpaksTask task."""

    def test_clean_up_download_location_task_name(self):
        """Test InstallFlatpaksTask name."""
        flatpak_manager = Mock()
        task = InstallFlatpaksTask(flatpak_manager)

        assert task.name == "Install Flatpaks"

    def test_clean_up_download_location_task_run(self):
        """Test InstallFlatpaksTask run."""
        flatpak_manager = Mock()

        task = InstallFlatpaksTask(flatpak_manager)
        task.run()

        flatpak_manager.install.assert_called_once()
